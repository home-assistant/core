"""Constants for the Silla Prism tests."""

BASE_TOPIC = "prism"

HELLO_TOPIC = "prism/hello"
HELLO_PAYLOAD = "Prism-A00006 3.2.77 (evsemd v1.1.1)"
SERIAL = "Prism-A00006"

# Retained status burst captured from a real Prism Solar (firmware 3.x), with a
# non-zero current so the milliamp-to-amp conversion is exercised.
RETAINED_BURST: list[tuple[str, str]] = [
    ("prism/1/state", "1"),
    ("prism/1/amp", "8000"),
    ("prism/1/wh", "3900"),
    ("prism/1/pilot", "6.0"),
    ("prism/1/user_amp", "6"),
    ("prism/1/volt", "236.0"),
    ("prism/1/w", "1760.0"),
    ("prism/1/wh_total", "719800"),
    ("prism/1/error", "0"),
    ("prism/1/mode", "2"),
    ("prism/1/session_time", "16030"),
    ("prism/0/info/temperature/core", "35"),
    ("prism/energy_data/power_grid", "2800"),
    ("prism/energy_data/power_solar", "0"),
    ("prism/energy_data/power_house", "0"),
]
