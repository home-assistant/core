"""Tests for the iCloud device tracker platform."""

from collections.abc import Awaitable, Callable

from pytest_homeassistant.typing import MagicMock

from homeassistant.components.icloud.const import (
    ATTR_ACCOUNT_FETCH_INTERVAL,
    ATTR_BATTERY,
    ATTR_BATTERY_STATUS,
    ATTR_DEVICE_STATUS,
    DOMAIN,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DEVICE, LOCATION, MAX_INTERVAL

TRACKER_UNIQUE_ID = "device1"


async def test_tracker_keeps_the_device_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """The tracker exposes the device attributes it carried before."""
    icloud_service.devices.add({**DEVICE, "location": LOCATION})

    await setup_entry(Platform.DEVICE_TRACKER)

    entity_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, TRACKER_UNIQUE_ID
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_ACCOUNT_FETCH_INTERVAL] == MAX_INTERVAL
    assert state.attributes[ATTR_BATTERY] == 80
    assert state.attributes[ATTR_BATTERY_STATUS] == "NotCharging"
    assert state.attributes[ATTR_DEVICE_STATUS] == "online"
