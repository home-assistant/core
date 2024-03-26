"""Tests for home_connect sensor entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

from homeconnect import HomeConnectAPI

from homeassistant.components.home_connect.const import DOMAIN, SIGNAL_UPDATE_ENTITIES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send

from .conftest import get_appliances

from tests.common import MockConfigEntry

TEST_HC_APP = "Dishwasher"


async def test_sensor(
    bypass_throttle,
    platforms,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
) -> None:
    """Test sensor entities."""
    platforms = [Platform.SENSOR]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    with patch.object(
        HomeConnectAPI,
        "get_appliances",
        side_effect=lambda: get_appliances(hass.data[DOMAIN][config_entry.entry_id]),
    ):
        assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED
    await hass.config_entries.async_forward_entry_setups(config_entry, platforms)

    (hc_app,) = (
        x["device"].appliance
        for x in hass.data[DOMAIN][config_entry.entry_id].devices
        if x["device"].appliance.type == TEST_HC_APP
    )

    dispatcher_send(hass, SIGNAL_UPDATE_ENTITIES, hc_app.haId)
    await hass.async_block_till_done()

    hc_app.status["BSH.Common.Option.RemainingProgramTime"] = {}

    dispatcher_send(hass, SIGNAL_UPDATE_ENTITIES, hc_app.haId)
    await hass.async_block_till_done()

    assert hass.states.is_state(
        "sensor.dishwasher_remaining_program_time", "unavailable"
    )

    hc_app.status.update({"BSH.Common.Option.RemainingProgramTime": {"value": 0}})
    dispatcher_send(hass, SIGNAL_UPDATE_ENTITIES, hc_app.haId)
    await hass.async_block_till_done()

    assert hass.states.is_state(
        "sensor.dishwasher_remaining_program_time", "unavailable"
    )

    hc_app.status.update(
        {
            "BSH.Common.Status.OperationState": {
                "value": "BSH.Common.EnumType.OperationState.Run"
            }
        }
    )

    dispatcher_send(hass, SIGNAL_UPDATE_ENTITIES, hc_app.haId)
    await hass.async_block_till_done()

    assert not hass.states.is_state(
        "sensor.dishwasher_remaining_program_time", "unavailable"
    )

    hc_app.status.update({"BSH.Common.Option.RemainingProgramTime": {"value": 3600}})

    dispatcher_send(hass, SIGNAL_UPDATE_ENTITIES, hc_app.haId)
    await hass.async_block_till_done()

    assert hass.states.is_state(
        "sensor.dishwasher_remaining_program_time", "unavailable"
    )
