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

# This stores device_class overrides for alert types that we know aren't "problems".
DEVICE_CLASS_OVERRIDES = {
    "alert_is_heating": BinarySensorDeviceClass.HEAT,
    "alert_install_pending": BinarySensorDeviceClass.UPDATE,
    "alert_roaming": None,
    "alert_is_power_save_idle": None,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up all binary sensors for this entry."""
    coordinator: StarlinkUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    alerts = coordinator.data[2]
    entities = []

    # Alerts may change over time, so we want to find available alerts and register them.
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

    # Add extra data not found in AlertDict
    entities.append(
        StarlinkBinarySensorEntity(
            coordinator=coordinator,
            description=StarlinkBinarySensorEntityDescription(
                key="currently_obstructed",
                name="Currently obstructed",
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                value_fn=lambda data: not data[0]["currently_obstructed"],
            ),
        )
    )

    async_add_entities(entities)
