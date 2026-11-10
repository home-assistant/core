"""Test the ADS entity base class."""

import asyncio
from unittest.mock import MagicMock

import pyads

from homeassistant.components.ads.const import STATE_KEY_STATE
from homeassistant.components.ads.entity import AdsEntity
from homeassistant.components.ads.hub import AdsHub
from homeassistant.core import HomeAssistant


def test_available() -> None:
    """Test availability reflects whether a state has been received."""
    entity = AdsEntity(MagicMock(spec=AdsHub), "test", "GVL.test")

    assert not entity.available

    entity._state_dict[STATE_KEY_STATE] = 1
    assert entity.available


async def test_refused_subscription_is_not_tracked(hass: HomeAssistant) -> None:
    """Test a subscription the hub refuses leaves no handle behind."""
    hub = MagicMock(spec=AdsHub)
    hub.add_device_notification.return_value = None
    entity = AdsEntity(hub, "test", "GVL.test")
    entity.hass = hass

    await entity.async_initialize_device("GVL.test", pyads.PLCTYPE_BOOL)

    assert not entity._notification_handles
    hub.delete_device_notification.assert_not_called()


async def test_subscription_landing_after_removal_is_dropped(
    hass: HomeAssistant,
) -> None:
    """Test a subscription that completes after removal is deleted again.

    Otherwise an entity removed while it was still subscribing would be left
    subscribed and pinned until the hub shuts down.
    """
    hub = MagicMock(spec=AdsHub)
    hub.add_device_notification.return_value = 7
    entity = AdsEntity(hub, "test", "GVL.test")
    entity.hass = hass
    entity.entity_id = "binary_sensor.test"

    await entity.async_will_remove_from_hass()
    await entity.async_initialize_device("GVL.test", pyads.PLCTYPE_BOOL)

    hub.delete_device_notification.assert_called_once_with(7)
    assert not entity._notification_handles


async def test_removal_stops_waiting_for_the_first_update(
    hass: HomeAssistant,
) -> None:
    """Test removal releases a subscription still waiting for its first value.

    The PLC will not push to a deleted notification, so the wait would only run
    into its timeout and hold up the entity being removed.
    """
    hub = MagicMock(spec=AdsHub)
    hub.add_device_notification.return_value = 7
    entity = AdsEntity(hub, "test", "GVL.test")
    entity.hass = hass
    entity.entity_id = "binary_sensor.test"

    task = hass.async_create_task(
        entity.async_initialize_device("GVL.test", pyads.PLCTYPE_BOOL)
    )
    async with asyncio.timeout(5):
        while not entity._notification_handles:
            await asyncio.sleep(0)

        await entity.async_will_remove_from_hass()
        await task
