"""Tests for the moon triggers."""

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import automation
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

_PHASE = "homeassistant.components.moon.helpers.moon.phase"


@pytest.fixture(autouse=True)
async def setup_moon(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the moon integration so its trigger platform is available."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def _arm(hass: HomeAssistant, options: dict[str, Any] | None = None) -> None:
    """Set up an automation with the moon phase_changed trigger."""
    trigger: dict[str, Any] = {"platform": "moon.phase_changed"}
    if options is not None:
        trigger["options"] = options
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": trigger,
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "phase": "{{ trigger.phase }}",
                        "previous_phase": "{{ trigger.previous_phase }}",
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()


def _next_local_midnight() -> datetime:
    """Return the next local midnight, when the phase trigger re-evaluates."""
    return dt_util.start_of_local_day() + timedelta(days=1)


async def test_phase_changed_fires_on_any_change(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the trigger fires on every phase change when unfiltered."""
    with patch(_PHASE, return_value=0.0):
        await _arm(hass)
    assert len(service_calls) == 0

    with patch(_PHASE, return_value=14.0):
        async_fire_time_changed(hass, _next_local_midnight())
        await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["phase"] == "full_moon"
    assert service_calls[0].data["previous_phase"] == "new_moon"


async def test_phase_changed_ignores_same_phase(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the trigger does not fire when the phase is unchanged."""
    with patch(_PHASE, return_value=14.0):
        await _arm(hass)
        async_fire_time_changed(hass, _next_local_midnight())
        await hass.async_block_till_done()

    assert len(service_calls) == 0


@pytest.mark.parametrize(
    ("new_value", "expected_calls"),
    [(14.0, 1), (5.0, 0)],
)
async def test_phase_changed_with_phase_filter(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    new_value: float,
    expected_calls: int,
) -> None:
    """Test the trigger only fires for the configured phase."""
    with patch(_PHASE, return_value=0.0):
        await _arm(hass, options={"phase": "full_moon"})

    with patch(_PHASE, return_value=new_value):
        async_fire_time_changed(hass, _next_local_midnight())
        await hass.async_block_till_done()

    assert len(service_calls) == expected_calls
