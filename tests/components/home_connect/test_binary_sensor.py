"""Tests for home_connect binary_sensor entities."""

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


async def test_binary_sensor(
    bypass_throttle,
    platforms,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
) -> None:
    """Test binary_sensor entities."""
    platforms = [Platform.BINARY_SENSOR]
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

    assert hass.states.is_state("binary_sensor.dishwasher_door", "off")

    hc_app.status.pop("BSH.Common.Status.DoorState")
    hc_app.status = {"BSH.Common.Status.DoorState": {"value": "NONEXISTENT_VALUE"}}

    dispatcher_send(hass, SIGNAL_UPDATE_ENTITIES, hc_app.haId)
    await hass.async_block_till_done()

    assert hass.states.is_state("binary_sensor.dishwasher_door", "unavailable")
