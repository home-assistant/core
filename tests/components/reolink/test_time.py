"""Test the Reolink time platform."""

from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from reolink_aio.enums import SpotlightModeEnum
from reolink_aio.exceptions import InvalidParameterError, ReolinkError

from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TIME, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import TEST_CAM_NAME

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_floodlight_schedule(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test the floodlight schedule start and end time entities."""
    reolink_host.whiteled_schedule.return_value = {
        "StartHour": 18,
        "StartMin": 0,
        "EndHour": 6,
        "EndMin": 30,
    }
    reolink_host.whiteled_mode_list.return_value = [SpotlightModeEnum.schedule.name]
    reolink_host.set_spotlight_lighting_schedule = AsyncMock()

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.TIME]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    start_id = f"{Platform.TIME}.{TEST_CAM_NAME}_floodlight_schedule_start"
    end_id = f"{Platform.TIME}.{TEST_CAM_NAME}_floodlight_schedule_end"

    assert hass.states.get(start_id).state == "18:00:00"
    assert hass.states.get(end_id).state == "06:30:00"

    # Setting the start time keeps the existing end time (6:30)
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: start_id, ATTR_TIME: time(20, 15)},
        blocking=True,
    )
    reolink_host.set_spotlight_lighting_schedule.assert_called_with(0, 6, 30, 20, 15)

    # Setting the end time keeps the existing start time (18:00)
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: end_id, ATTR_TIME: time(7, 0)},
        blocking=True,
    )
    reolink_host.set_spotlight_lighting_schedule.assert_called_with(0, 7, 0, 18, 0)

    reolink_host.set_spotlight_lighting_schedule.side_effect = ReolinkError(
        "Test error"
    )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: start_id, ATTR_TIME: time(20, 15)},
            blocking=True,
        )

    reolink_host.set_spotlight_lighting_schedule.side_effect = InvalidParameterError(
        "Test error"
    )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: start_id, ATTR_TIME: time(20, 15)},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_floodlight_schedule_unknown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test the floodlight schedule entities when no schedule is available."""
    reolink_host.whiteled_mode_list.return_value = [SpotlightModeEnum.schedule.name]
    reolink_host.whiteled_schedule.return_value = None

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.TIME]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    start_id = f"{Platform.TIME}.{TEST_CAM_NAME}_floodlight_schedule_start"
    assert hass.states.get(start_id).state == STATE_UNKNOWN
