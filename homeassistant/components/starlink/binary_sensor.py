"""Contains sensors exposed by the Starlink integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import StarlinkUpdateCoordinator
from .entity import StarlinkBinarySensorEntity, StarlinkBinarySensorEntityDescription

DEVICE_CLASS_OVERRIDES = {
    "alert_is_heating": BinarySensorDeviceClass.HEAT,
    "alert_install_pending": BinarySensorDeviceClass.UPDATE,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up all binary sensors for this entry."""
    coordinator: StarlinkUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    alerts = coordinator.data[2]
    entities = []

    for key, _ in alerts.items():
        entities.append(
            StarlinkBinarySensorEntity(
                coordinator=coordinator,
                description=StarlinkBinarySensorEntityDescription(
                    key=key,
                    name=key.removeprefix("alert_").replace("_", " ").capitalize(),
                    device_class=DEVICE_CLASS_OVERRIDES.get(
                        key, BinarySensorDeviceClass.PROBLEM
                    ),
                    entity_category=EntityCategory.DIAGNOSTIC,
                    value_fn=lambda data, key=key: data[2][key],  # type:ignore[misc]
                ),
            )
        )

    async_add_entities(entities)
