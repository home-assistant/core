"""Tests for the moon conditions."""

from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import condition
from homeassistant.helpers.typing import ConfigType

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
async def setup_moon(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the moon integration so its condition platform is available."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def _evaluate(
    hass: HomeAssistant, config: ConfigType, phase_value: float
) -> bool | None:
    """Validate and evaluate a condition for a mocked astral phase value."""
    with patch(
        "homeassistant.components.moon.helpers.moon.phase", return_value=phase_value
    ):
        config = await condition.async_validate_condition_config(hass, config)
        checker = await condition.async_from_config(hass, config)
        return checker(hass)


@pytest.mark.parametrize(
    ("config", "phase_value", "expected"),
    [
        pytest.param(
            {"condition": "moon.is_phase", "options": {"phase": "full_moon"}},
            14.0,
            True,
            id="is_phase-match",
        ),
        pytest.param(
            {"condition": "moon.is_phase", "options": {"phase": "full_moon"}},
            0.0,
            False,
            id="is_phase-mismatch",
        ),
        pytest.param(
            {"condition": "moon.is_waxing"}, 5.0, True, id="waxing-before-full"
        ),
        pytest.param({"condition": "moon.is_waxing"}, 0.0, True, id="waxing-new-moon"),
        pytest.param({"condition": "moon.is_waxing"}, 14.0, False, id="waxing-at-full"),
        pytest.param(
            {"condition": "moon.is_waxing"}, 20.0, False, id="waxing-after-full"
        ),
        pytest.param(
            {"condition": "moon.is_waning"}, 20.0, True, id="waning-after-full"
        ),
        pytest.param({"condition": "moon.is_waning"}, 14.0, True, id="waning-at-full"),
        pytest.param(
            {"condition": "moon.is_waning"}, 5.0, False, id="waning-before-full"
        ),
        pytest.param({"condition": "moon.is_waning"}, 0.0, False, id="waning-new-moon"),
    ],
)
async def test_conditions(
    hass: HomeAssistant,
    config: ConfigType,
    phase_value: float,
    expected: bool,
) -> None:
    """Test the moon conditions against a mocked phase value."""
    assert await _evaluate(hass, config, phase_value) is expected


async def test_is_phase_rejects_unknown_phase(hass: HomeAssistant) -> None:
    """Test that the is_phase condition rejects an unknown phase."""
    with pytest.raises(vol.Invalid):
        await condition.async_validate_condition_config(
            hass, {"condition": "moon.is_phase", "options": {"phase": "not_a_phase"}}
        )
