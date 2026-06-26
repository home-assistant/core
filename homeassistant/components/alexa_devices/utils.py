"""Utils for Alexa Devices."""

from aioamazondevices.const.devices import SPEAKER_GROUP_FAMILY
from aioamazondevices.const.schedules import (
    NOTIFICATION_ALARM,
    NOTIFICATION_REMINDER,
    NOTIFICATION_TIMER,
)

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from .const import _LOGGER, DOMAIN
from .coordinator import AmazonDevicesCoordinator


async def async_update_unique_id(
    hass: HomeAssistant,
    coordinator: AmazonDevicesCoordinator,
    platform: str,
    old_key: str,
    new_key: str,
) -> None:
    """Update unique id for entities created with old format."""
    entity_registry = er.async_get(hass)

    for serial_num in coordinator.data:
        unique_id = f"{serial_num}-{old_key}"
        if entity_id := entity_registry.async_get_entity_id(
            platform, DOMAIN, unique_id
        ):
            _LOGGER.debug("Updating unique_id for %s", entity_id)
            new_unique_id = unique_id.replace(old_key, new_key)

            # Update the registry with the new unique_id
            entity_registry.async_update_entity(entity_id, new_unique_id=new_unique_id)


async def async_remove_entity_from_virtual_group(
    hass: HomeAssistant,
    coordinator: AmazonDevicesCoordinator,
    platform: str,
    key: str,
) -> None:
    """Remove entity from virtual group."""
    entity_registry = er.async_get(hass)

    for serial_num in coordinator.data:
        unique_id = f"{serial_num}-{key}"
        entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
        is_group = coordinator.data[serial_num].device_family == SPEAKER_GROUP_FAMILY
        if entity_id and is_group:
            entity_registry.async_remove(entity_id)
            _LOGGER.debug("Removed entity '%s' from virtual group", entity_id)


async def async_remove_unsupported_notification_sensors(
    hass: HomeAssistant,
    coordinator: AmazonDevicesCoordinator,
) -> None:
    """Remove notification sensors from unsupported devices."""
    entity_registry = er.async_get(hass)

    for serial_num in coordinator.data:
        for notification_key in (
            NOTIFICATION_ALARM,
            NOTIFICATION_REMINDER,
            NOTIFICATION_TIMER,
        ):
            unique_id = f"{serial_num}-{notification_key}"
            entity_id = entity_registry.async_get_entity_id(
                SENSOR_DOMAIN, DOMAIN, unique_id=unique_id
            )
            is_unsupported = not coordinator.data[serial_num].notifications_supported

            if entity_id and is_unsupported:
                entity_registry.async_remove(entity_id)
                _LOGGER.debug("Removed unsupported notification sensor %s", entity_id)
