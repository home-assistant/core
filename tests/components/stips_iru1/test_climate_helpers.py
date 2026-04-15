"""Helper-level tests for stips_iru1 climate module."""

from homeassistant.components.climate.const import HVACMode
from homeassistant.components.stips_iru1.climate import (
    _extract_learned_ac_signals,
    _fan_to_name,
    _mode_to_hvac,
    _normalize_swing_mode,
    _pick_best_learned_signal,
    _split_swing_mode,
)


def test_swing_mode_roundtrip():
    """Swing mode split/normalize should map expected combinations."""
    assert _split_swing_mode("off") == (0, 0)
    assert _split_swing_mode("vertical") == (1, 0)
    assert _split_swing_mode("horizontal") == (0, 1)
    assert _split_swing_mode("both") == (1, 1)

    assert _normalize_swing_mode(0, 0) == "off"
    assert _normalize_swing_mode(1, 0) == "vertical"
    assert _normalize_swing_mode(0, 1) == "horizontal"
    assert _normalize_swing_mode(1, 1) == "both"


def test_mode_and_fan_normalization():
    """Mode/fan helper normalization should accept aliases and ints."""
    assert _mode_to_hvac("fan_only") == HVACMode.FAN_ONLY
    assert _mode_to_hvac("cool") == HVACMode.COOL
    assert _fan_to_name("4") == "high"
    assert _fan_to_name("med") == "medium"


def test_learned_ac_signal_extraction_and_pick():
    """Learned AC helpers should parse signals and pick best match."""
    remote_snapshot = {
        "model": {
            "frequency": 38000,
            "signals": [
                {"mode": "cool", "temperature": 22, "fanSpeed": "medium", "signal": "A"},
                {"mode": "cool", "temperature": 23, "fanSpeed": "medium", "signal": "B"},
            ],
            "powerOnSignal": "PON",
            "powerOffSignal": "POFF",
        }
    }
    entries, power_on, power_off, freq = _extract_learned_ac_signals(remote_snapshot)
    assert len(entries) == 2
    assert power_on == "PON"
    assert power_off == "POFF"
    assert freq == 38000

    picked = _pick_best_learned_signal(entries, HVACMode.COOL, 23, "medium")
    assert picked == "B"
