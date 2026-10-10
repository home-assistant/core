"""Test the ADS entity base class."""

from unittest.mock import MagicMock, patch

import pyads

from homeassistant.components.ads.const import STATE_KEY_STATE
from homeassistant.components.ads.entity import AdsEntity
from homeassistant.components.ads.hub import AdsHub
from homeassistant.core import HomeAssistant


def test_registers_with_hub() -> None:
    """Test the entity registers itself with the hub on init."""
    hub = MagicMock(spec=AdsHub)

    entity = AdsEntity(hub, "test", "GVL.test")

    hub.register_device.assert_called_once_with(entity)


def test_available() -> None:
    """Test availability reflects whether a state has been received."""
    entity = AdsEntity(MagicMock(spec=AdsHub), "test", "GVL.test")

    assert not entity.available

    entity._state_dict[STATE_KEY_STATE] = 1
    assert entity.available


def test_mark_unavailable_before_added_to_hass() -> None:
    """Test marking unavailable before the entity is added to hass."""
    entity = AdsEntity(MagicMock(spec=AdsHub), "test", "GVL.test")
    entity._state_dict[STATE_KEY_STATE] = 1

    entity.mark_unavailable()

    assert not entity.available


def test_mark_unavailable_schedules_update(hass: HomeAssistant) -> None:
    """Test marking unavailable schedules a state update once added to hass."""
    entity = AdsEntity(MagicMock(spec=AdsHub), "test", "GVL.test")
    entity.hass = hass
    entity._state_dict[STATE_KEY_STATE] = 1

    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.mark_unavailable()

    mock_schedule.assert_called_once()
    assert not entity.available


def test_mark_unavailable_clears_every_cached_state_field() -> None:
    """Test marking unavailable clears secondary state, like a cover's position."""
    entity = AdsEntity(MagicMock(spec=AdsHub), "test", "GVL.test")
    entity._state_dict[STATE_KEY_STATE] = 1
    entity._state_dict["position"] = 50

    entity.mark_unavailable()

    assert entity._state_dict == {STATE_KEY_STATE: None, "position": None}


async def test_unregisters_when_removed(hass: HomeAssistant) -> None:
    """Test the entity unregisters itself from the hub when removed."""
    hub = MagicMock(spec=AdsHub)
    entity = AdsEntity(hub, "test", "GVL.test")
    entity.hass = hass
    entity.entity_id = "binary_sensor.test"

    await entity.async_remove()

    hub.unregister_device.assert_called_once_with(entity)


def test_unregisters_when_not_added() -> None:
    """Test an entity the platform refuses to add is dropped from the hub."""
    hub = MagicMock(spec=AdsHub)
    entity = AdsEntity(hub, "test", "GVL.test")

    entity.add_to_platform_abort()

    hub.unregister_device.assert_called_once_with(entity)


def test_rebind() -> None:
    """Test rebinding an entity registers it with the new hub."""
    entity = AdsEntity(MagicMock(spec=AdsHub), "test", "GVL.test")

    new_hub = MagicMock(spec=AdsHub)
    entity.rebind(new_hub)

    assert entity._ads_hub is new_hub
    new_hub.register_device.assert_called_once_with(entity)


async def test_subscription_landing_after_removal_is_dropped(
    hass: HomeAssistant,
) -> None:
    """Test a subscription that completes after removal is deleted again.

    A reload resubscribes in the background, so an entity disabled during that
    window would otherwise be left subscribed and pinned until hub shutdown.
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
