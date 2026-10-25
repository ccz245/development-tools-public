"""Current weather and today's outlook per city, from Open-Meteo (free, no key)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
PARTS_OF_DAY = {"Morn": 9, "Aft": 15, "Eve": 20}

# WMO weather code -> (label, day icon, night icon). Icons are Material Icons names.
CODES: dict[int, tuple[str, str, str]] = {
    0: ("Clear", "wb_sunny", "bedtime"),
    1: ("Mostly clear", "wb_sunny", "bedtime"),
    2: ("Partly cloudy", "wb_cloudy", "nights_stay"),
    3: ("Cloudy", "cloud", "cloud"),
    45: ("Fog", "foggy", "foggy"),
    48: ("Fog", "foggy", "foggy"),
    51: ("Drizzle", "grain", "grain"),
    53: ("Drizzle", "grain", "grain"),
    55: ("Drizzle", "grain", "grain"),
    56: ("Freezing drizzle", "grain", "grain"),
    57: ("Freezing drizzle", "grain", "grain"),
    61: ("Light rain", "water_drop", "water_drop"),
    63: ("Rain", "water_drop", "water_drop"),
    65: ("Heavy rain", "water_drop", "water_drop"),
    66: ("Freezing rain", "water_drop", "water_drop"),
    67: ("Freezing rain", "water_drop", "water_drop"),
    71: ("Light snow", "ac_unit", "ac_unit"),
    73: ("Snow", "ac_unit", "ac_unit"),
    75: ("Heavy snow", "ac_unit", "ac_unit"),
    77: ("Snow grains", "ac_unit", "ac_unit"),
    80: ("Showers", "water_drop", "water_drop"),
    81: ("Showers", "water_drop", "water_drop"),
    82: ("Heavy showers", "water_drop", "water_drop"),
    85: ("Snow showers", "ac_unit", "ac_unit"),
    86: ("Snow showers", "ac_unit", "ac_unit"),
    95: ("Thunderstorm", "thunderstorm", "thunderstorm"),
    96: ("Thunderstorm", "thunderstorm", "thunderstorm"),
    99: ("Thunderstorm", "thunderstorm", "thunderstorm"),
}


def describe(code: int, is_day: bool) -> tuple[str, str]:
    """(label, icon) for a WMO code."""
    name, day_icon, night_icon = CODES.get(code, ("Unknown", "help_outline", "help_outline"))
    return name, day_icon if is_day else night_icon


@dataclass
class Slot:
    temp: float
    code: int
    is_day: bool


@dataclass
class Weather:
    temp: float
    code: int
    is_day: bool
    low: float
    high: float
    parts: dict[str, Slot]  # Morn / Aft / Eve
    precip: int | None  # today's max precipitation probability, %
    sunrise: str  # HH:MM local to the city
    sunset: str


def parse(data: dict) -> Weather:
    current = data["current"]
    daily = data["daily"]
    hourly = data["hourly"]
    today = current["time"][:10]  # the city's own date, since the request asks for timezone=auto
    day = daily["time"].index(today) if today in daily["time"] else 0
    sunrise, sunset = daily["sunrise"][day], daily["sunset"][day]

    parts: dict[str, Slot] = {}
    for name, hour in PARTS_OF_DAY.items():
        stamp = f"{today}T{hour:02d}:00"
        if stamp in hourly["time"]:
            i = hourly["time"].index(stamp)
            parts[name] = Slot(hourly["temperature_2m"][i], hourly["weather_code"][i], sunrise[11:16] <= f"{hour:02d}:00" < sunset[11:16])

    precip = daily.get("precipitation_probability_max", [None])[day]
    return Weather(
        temp=current["temperature_2m"],
        code=current["weather_code"],
        is_day=bool(current["is_day"]),
        low=daily["temperature_2m_min"][day],
        high=daily["temperature_2m_max"][day],
        parts=parts,
        precip=int(precip) if precip is not None else None,
        sunrise=sunrise[11:16],
        sunset=sunset[11:16],
    )


def fetch(lat: float, lon: float, timeout: float = 10.0) -> Weather:
    response = httpx.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code,is_day",
            "hourly": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": 2,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return parse(response.json())


def fetched_at() -> str:
    return datetime.now().strftime("%H:%M:%S")
