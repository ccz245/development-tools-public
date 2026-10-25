"""Tests for the data sources: parsing and arithmetic only, no network and no system changes."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from windows_console.config import APP_DIR, JsonState, _merge
from windows_console.sources import claude_usage, hotstrings, power, transcripts, weather
from windows_console.sources.tasks import LocalProvider, export_notes, import_notes, parse_quick_add, resolve_due
from windows_console.ui import fmt

PRICING = claude_usage.Pricing.load(APP_DIR / "pricing.json")


# --- config -----------------------------------------------------------------------------------

def test_merge_overlays_nested_objects_and_replaces_lists():
    base = {"a": {"x": 1, "y": 2}, "list": [1, 2], "keep": True}
    merged = _merge(base, {"a": {"y": 3}, "list": [9]})
    assert merged == {"a": {"x": 1, "y": 3}, "list": [9], "keep": True}


def test_json_state_round_trips(tmp_path: Path):
    state = JsonState(tmp_path / "s.json", {"dark": True})
    state.set("order", ["b", "a"])
    again = JsonState(tmp_path / "s.json", {"dark": True})
    assert again.get("order") == ["b", "a"] and again.get("dark") is True


# --- Claude usage -----------------------------------------------------------------------------

def test_pricing_matches_longest_prefix():
    assert PRICING.rates("claude-opus-4-8")["input"] == 5.0
    assert PRICING.rates("claude-opus-4-20250514")["input"] == 15.0
    assert PRICING.rates("claude-sonnet-4-5-20250929")["input"] == 3.0
    assert PRICING.rates("something-new") == PRICING.rates("claude-opus-5-5")


def test_cost_counts_each_token_kind_at_its_rate():
    usage = {
        "input_tokens": 1_000_000,
        "output_tokens": 1_000_000,
        "cache_read_input_tokens": 1_000_000,
        "cache_creation_input_tokens": 2_000_000,
        "cache_creation": {"ephemeral_5m_input_tokens": 1_000_000, "ephemeral_1h_input_tokens": 1_000_000},
    }
    # Opus 5.5: 4 + 20 + 0.20 + 5 + 8
    assert PRICING.cost("claude-opus-5-5", usage) == pytest.approx(37.2)
    assert PRICING.cost("claude-opus-5-5", usage, "fast") == pytest.approx(74.4)


def test_cost_without_split_treats_cache_writes_as_five_minute():
    usage = {"cache_creation_input_tokens": 1_000_000}
    assert PRICING.cost("claude-sonnet-5-5", usage) == pytest.approx(2.5)


def _line(msg_id: str, ts: str, model: str = "claude-opus-5-5", out: int = 1_000_000) -> bytes:
    record = {"type": "assistant", "timestamp": ts, "requestId": "r" + msg_id,
              "message": {"id": msg_id, "model": model, "usage": {"output_tokens": out}}}
    return (json.dumps(record) + "\n").encode()


def test_usage_log_dedupes_and_reads_incrementally(tmp_path: Path):
    log = tmp_path / "project" / "session.jsonl"
    log.parent.mkdir()
    log.write_bytes(_line("m1", "2026-10-20T10:00:00Z") + _line("m1", "2026-10-20T10:00:00Z") + b'{"type":"user"}\n')
    reader = claude_usage.UsageLog([tmp_path], PRICING)
    assert len(reader.scan()) == 1
    with log.open("ab") as handle:
        handle.write(_line("m2", "2026-10-20T11:00:00Z") + b'{"type":"assistant","timest')  # half-written line
    assert [e.cost for e in reader.scan()] == [20.0, 20.0]


def test_usage_cache_resumes_and_resets_on_new_pricing(tmp_path: Path):
    log = tmp_path / "logs" / "s.jsonl"
    log.parent.mkdir()
    log.write_bytes(_line("m1", "2026-10-20T10:00:00Z"))
    cache = tmp_path / "cache.json"
    claude_usage.UsageLog([log.parent], PRICING, cache, "v1").scan()
    resumed = claude_usage.UsageLog([log.parent], PRICING, cache, "v1")
    assert len(resumed.entries) == 1 and len(resumed.scan()) == 1  # nothing re-read, nothing doubled
    assert claude_usage.UsageLog([log.parent], PRICING, cache, "v2").entries == []


def test_synthetic_lines_are_ignored():
    assert claude_usage.parse_line(_line("x", "2026-10-20T10:00:00Z", model="<synthetic>"), PRICING) is None


def test_daily_costs_and_cumulative():
    today = date(2026, 10, 24)
    local_noon = lambda d: datetime(d.year, d.month, d.day, 12).astimezone(timezone.utc)
    entries = [
        claude_usage.Entry(local_noon(today), "m", 3.0),
        claude_usage.Entry(local_noon(today - timedelta(days=2)), "m", 2.0),
        claude_usage.Entry(local_noon(today - timedelta(days=40)), "m", 99.0),
    ]
    daily = claude_usage.daily_costs(entries, 7, today)
    assert len(daily) == 7 and daily[-1] == (today, 3.0) and daily[-3][1] == 2.0
    assert claude_usage.cumulative(daily)[-1][1] == 5.0


def test_current_block_starts_on_the_hour_and_lasts_five_hours():
    t = datetime(2026, 10, 24, 9, 40, tzinfo=timezone.utc)
    entries = [claude_usage.Entry(t, "m", 1), claude_usage.Entry(t + timedelta(hours=1), "m", 1)]
    start, end = claude_usage.current_block(entries, t + timedelta(hours=2))
    assert start.hour == 9 and start.minute == 0 and end - start == timedelta(hours=5)
    assert claude_usage.current_block(entries, t + timedelta(hours=6)) is None


# --- power ------------------------------------------------------------------------------------

POWERCFG = """Power Setting GUID: 3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e  (Turn off display after)
    Minimum Possible Setting: 0x00000000
    Maximum Possible Setting: 0xffffffff
    Possible Settings increment: 0x00000001
    Possible Settings units: Seconds
  Current AC Power Setting Index: 0x00000000
  Current DC Power Setting Index: 0x00000708
"""


def test_powercfg_parse_takes_last_two_values():
    assert power.parse_query(POWERCFG) == (0, 1800)
    assert power.parse_query("nothing here") is None


def test_timeout_labels():
    assert [power.label(m) for m in (0, 30, 60, 120)] == ["Never", "30 min", "1 hour", "2 hours"]


# --- weather ----------------------------------------------------------------------------------

def test_weather_parse_picks_city_local_day_and_parts():
    hours = [f"2026-10-24T{h:02d}:00" for h in range(24)]
    data = {
        "current": {"time": "2026-10-24T17:30", "temperature_2m": 8.4, "weather_code": 53, "is_day": 0},
        "hourly": {"time": hours, "temperature_2m": list(range(24)), "weather_code": [3] * 24},
        "daily": {"time": ["2026-10-24", "2026-10-25"], "temperature_2m_min": [3.0, 4.0], "temperature_2m_max": [9.0, 10.0],
                  "sunrise": ["2026-10-24T07:47", "x"], "sunset": ["2026-10-24T18:07", "x"],
                  "precipitation_probability_max": [63, 10]},
    }
    w = weather.parse(data)
    assert (w.low, w.high, w.precip, w.sunrise, w.sunset) == (3.0, 9.0, 63, "07:47", "18:07")
    assert w.parts["Morn"].temp == 9 and w.parts["Eve"].is_day is False
    assert weather.describe(53, False)[0] == "Drizzle"


# --- tasks ------------------------------------------------------------------------------------

def test_quick_add_parses_every_token():
    q = parse_quick_add('Send the plan p2 #"Platform migration" @waiting +Kick_off due:fri')
    assert q.content == "Send the plan"
    assert (q.priority, q.project, q.labels, q.owner, q.due) == (2, "Platform migration", ["waiting"], "Kick off", "fri")


def test_quick_add_leaves_plain_words_alone():
    q = parse_quick_add("Review p10 and #3 email")
    assert q.content == "Review p10 and email" and q.project == "3" and q.priority == 4


def test_resolve_due():
    saturday = date(2026, 10, 24)
    assert resolve_due("today", saturday) == "2026-10-24"
    assert resolve_due("fri", saturday) == "2026-10-30"
    assert resolve_due("sat", saturday) == "2026-10-31"  # a weekday always means the next one
    assert resolve_due("2026-12-01", saturday) == "2026-12-01"
    assert resolve_due("next week", saturday) is None


def test_local_provider_add_complete_and_priority(tmp_path: Path):
    provider = LocalProvider(tmp_path / "tasks.json")
    task = provider.add(parse_quick_add("Write report p1 #Ops"))
    assert provider.list()[0].priority == 1 and provider.list()[0].project == "Ops"
    provider.set_priority(task.id, 3)
    assert provider.list()[0].priority == 3
    provider.complete(task.id)
    assert provider.list() == []


def test_notes_round_trip(tmp_path: Path):
    provider = LocalProvider(tmp_path / "tasks.json")
    provider.add(parse_quick_add("Call the vendor p2 #Ops"))
    notes = tmp_path / "notes.md"
    export_notes(notes, provider.list())
    assert import_notes(notes) == ["Call the vendor p2"]


# --- transcripts ------------------------------------------------------------------------------

def test_transcripts_accept_several_field_spellings(tmp_path: Path):
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join([
        json.dumps({"ts": "2026-10-24T17:27:00", "text": "first", "stt_s": 0.6, "post_s": 2.1}),
        json.dumps({"timestamp": 1792890000, "transcript": "second"}),
        "not json",
        json.dumps({"text": "no time"}),
    ]), encoding="utf-8")
    items = transcripts.TranscriptStore(path).load()
    assert [i.text for i in items][0:2] in (["second", "first"], ["first", "second"])
    first = next(i for i in items if i.text == "first")
    assert (first.first, first.second) == (0.6, 2.1)
    assert len(items) == 2


# --- hotstrings -------------------------------------------------------------------------------

def test_key_labels():
    assert hotstrings.key_label("#b") == "Win+B"
    assert hotstrings.key_label("^!{F13}") == "Ctrl+Alt+F13"
    assert hotstrings.key_label("CapsLock") == "CapsLock"


def test_rendered_script_escapes_special_characters():
    spec = {
        "prompts": [{"trigger": ";q", "label": "Q", "text": 'Say "hi" `now`\nthen stop'}],
        "text": [{"trigger": "sig", "text": "Thanks! ;-)\n{me}"}],
        "hotkeys": [{"keys": "#b", "app": "Code.exe", "label": "New", "send": "^!{F13}"}],
    }
    script = hotstrings.render_ahk(spec, "Ada")
    assert ':*X:;q::PasteText("Say `"hi`" ``now```nthen stop")' in script
    assert "::sig::Thanks{!} `;-){Enter}Ada" in script
    assert '#HotIf WinActive("ahk_exe Code.exe")' in script and '#b::Send "^!{F13}"' in script


def test_shipped_hotstrings_file_is_complete():
    spec = hotstrings.load(APP_DIR / "hotstrings.json")
    assert (len(spec["prompts"]), len(spec["text"]), len(spec["hotkeys"])) == (11, 14, 6)


# --- processes --------------------------------------------------------------------------------

def test_snapshot_sees_this_process_with_its_start_time():
    import os
    import psutil
    from windows_console.sources import procs

    me = next(p for p in procs.snapshot() if p.pid == os.getpid())
    assert me.name.lower().startswith("python")
    assert abs(me.created - psutil.Process().create_time()) < 2
    assert me.working_set > 0


def test_sampler_reports_cpu_between_samples():
    from windows_console.sources import machine

    sampler = machine.Sampler()
    sampler.sample()
    sum(i * i for i in range(2_000_000))  # burn a little CPU in this process
    snap = sampler.sample(top=400)
    assert snap.processes > 10 and snap.top_memory
    assert any(p.cpu > 0 for p in snap.top)


# --- formatting -------------------------------------------------------------------------------

def test_formatters():
    assert fmt.duration(timedelta(hours=4, minutes=16)) == "4h 16m"
    assert fmt.duration(timedelta(days=1, hours=9, minutes=5)) == "1d 9h"
    assert fmt.idle(6) == "6s" and fmt.idle(250) == "4m 10s"
    assert fmt.money(303.4) == "$303" and fmt.money(1775) == "$1,775" and fmt.money(0.5) == "$0.50"
    now = datetime(2026, 10, 24, 18, 0)
    assert fmt.stamp(datetime(2026, 10, 24, 17, 27), now) == "17:27"
    assert fmt.stamp(datetime(2026, 10, 23, 16, 29), now) == "Oct 23 16:29"
