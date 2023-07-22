"""Support for Hydrawise sprinkler binary sensors."""
from __future__ import annotations

from pydrawise.legacy import LegacyHydrawise
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, LOGGER
from .coordinator import HydrawiseDataUpdateCoordinator
from .entity import HydrawiseEntity

BINARY_SENSOR_STATUS = BinarySensorEntityDescription(
    key="status",
    name="Status",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="is_watering",
        name="Watering",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
)

BINARY_SENSOR_KEYS: list[str] = [
    desc.key for desc in (BINARY_SENSOR_STATUS, *BINARY_SENSOR_TYPES)
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=BINARY_SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(BINARY_SENSOR_KEYS)]
        )
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a sensor for a Hydrawise device."""
    coordinator: HydrawiseDataUpdateCoordinator = hass.data[DOMAIN]
    hydrawise: LegacyHydrawise = coordinator.api
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]

    entities = []
    if BINARY_SENSOR_STATUS.key in monitored_conditions:
        entities.append(
            HydrawiseBinarySensor(
                data=hydrawise.current_controller,
                coordinator=coordinator,
                description=BINARY_SENSOR_STATUS,
            )
        )

    # create a sensor for each zone
    for zone in hydrawise.relays:
        for description in BINARY_SENSOR_TYPES:
            if description.key not in monitored_conditions:
                continue
            entities.append(
                HydrawiseBinarySensor(
                    data=zone, coordinator=coordinator, description=description
                )
            )

    add_entities(entities, True)


class HydrawiseBinarySensor(HydrawiseEntity, BinarySensorEntity):
    """A sensor implementation for Hydrawise device."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the state."""
        LOGGER.debug("Updating Hydrawise binary sensor: %s", self.name)
        if self.entity_description.key == "status":
            self._attr_is_on = self.coordinator.api.status == "All good!"
        elif self.entity_description.key == "is_watering":
            relay_data = self.coordinator.api.relays[self.data["relay"] - 1]
            self._attr_is_on = relay_data["timestr"] == "Now"
        super()._handle_coordinator_update()
