# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "nicegui>=3.18,<4",
#     "psutil>=7",
#     "pywebview>=5",
#     "tzdata",
# ]
# ///
"""NiceGUI Windows Console.

    uv run console.py              native window
    uv run console.py --browser    in the default browser
    uv run console.py --demo       with generic sample data
"""

from windows_console.app import main

if __name__ in {"__main__", "__mp_main__"}:
    main()
