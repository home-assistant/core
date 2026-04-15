"""Helper-level tests for stips_iru1 climate module."""

from homeassistant.components.climate.const import HVACMode
from homeassistant.components.stips_iru1 import climate as stips_climate


def test_swing_mode_roundtrip() -> None:
    """Swing mode split/normalize should map expected combinations."""
    assert stips_climate._split_swing_mode("off") == (0, 0)
    assert stips_climate._split_swing_mode("vertical") == (1, 0)
    assert stips_climate._split_swing_mode("horizontal") == (0, 1)
    assert stips_climate._split_swing_mode("both") == (1, 1)

    assert stips_climate._normalize_swing_mode(0, 0) == "off"
    assert stips_climate._normalize_swing_mode(1, 0) == "vertical"
    assert stips_climate._normalize_swing_mode(0, 1) == "horizontal"
    assert stips_climate._normalize_swing_mode(1, 1) == "both"


def test_mode_and_fan_normalization() -> None:
    """Mode/fan helper normalization should accept aliases and ints."""
    assert stips_climate._mode_to_hvac("fan_only") == HVACMode.FAN_ONLY
    assert stips_climate._mode_to_hvac("cool") == HVACMode.COOL
    assert stips_climate._fan_to_name("4") == "high"
    assert stips_climate._fan_to_name("med") == "medium"


def test_learned_ac_signal_extraction_and_pick() -> None:
    """Learned AC helpers should parse signals and pick best match."""
    remote_snapshot = {
        "model": {
            "frequency": 38000,
            "signals": [
                {
                    "mode": "cool",
                    "temperature": 22,
                    "fanSpeed": "medium",
                    "signal": "A",
                },
                {
                    "mode": "cool",
                    "temperature": 23,
                    "fanSpeed": "medium",
                    "signal": "B",
                },
            ],
            "powerOnSignal": "PON",
            "powerOffSignal": "POFF",
        }
    }
    entries, power_on, power_off, freq = stips_climate._extract_learned_ac_signals(
        remote_snapshot
    )
    assert len(entries) == 2
    assert power_on == "PON"
    assert power_off == "POFF"
    assert freq == 38000

    picked = stips_climate._pick_best_learned_signal(
        entries, HVACMode.COOL, 23, "medium"
    )
    assert picked == "B"
