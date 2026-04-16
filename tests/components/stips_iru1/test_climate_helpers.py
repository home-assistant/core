"""Helper-level tests for stips_iru1 climate module."""

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.stips_iru1 import climate as stips_climate
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


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


async def test_learned_ac_rejects_unsupported_fan_mode(
    hass: HomeAssistant,
) -> None:
    """Unsupported fan mode should raise instead of silently mapping values."""
    entity = stips_climate.StipsIruLearnedAcClimate(
        hass=hass,
        device_unique_name="stips-iru1-abc123",
        device_name="IR Unit",
        device_ip="",
        device_mac="",
        device_online=True,
        remote_id="1",
        friendly_name="Living Room",
        remote_snapshot={
            "type": "LearnedAc",
            "model": {
                "frequency": 38000,
                "signals": [
                    {
                        "mode": "cool",
                        "temperature": 24,
                        "fanSpeed": "medium",
                        "signal": "SIGNAL",
                    }
                ],
            },
        },
    )

    with pytest.raises(HomeAssistantError, match="Unsupported fan mode"):
        await entity.async_set_fan_mode("unsupported")
