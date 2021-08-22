"""Support for Toon binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ToonDataUpdateCoordinator
from .models import (
    ToonBoilerDeviceEntity,
    ToonBoilerModuleDeviceEntity,
    ToonDisplayDeviceEntity,
    ToonEntity,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up a Toon binary sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        description.cls(coordinator, description)
        for description in BINARY_SENSOR_ENTITIES
    ]
    if coordinator.data.thermostat.have_opentherm_boiler:
        entities.extend(
            [
                description.cls(coordinator, description)
                for description in BINARY_SENSOR_ENTITIES_BOILER
            ]
        )

    async_add_entities(entities, True)


class ToonBinarySensor(ToonEntity, BinarySensorEntity):
    """Defines an Toon binary sensor."""

    entity_description: ToonBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: ToonDataUpdateCoordinator,
        description: ToonBinarySensorEntityDescription,
    ) -> None:
        """Initialize the Toon sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = (
            # This unique ID is a bit ugly and contains unneeded information.
            # It is here for legacy / backward compatible reasons.
            f"{DOMAIN}_{coordinator.data.agreement.agreement_id}_binary_sensor_{description.key}"
        )

    @property
    def is_on(self) -> bool | None:
        """Return the status of the binary sensor."""
        section = getattr(self.coordinator.data, self.entity_description.section)
        value = getattr(section, self.entity_description.measurement)

        if value is None:
            return None

        if self.entity_description.inverted:
            return not value

        return value


class ToonBoilerBinarySensor(ToonBinarySensor, ToonBoilerDeviceEntity):
    """Defines a Boiler binary sensor."""


class ToonDisplayBinarySensor(ToonBinarySensor, ToonDisplayDeviceEntity):
    """Defines a Toon Display binary sensor."""


class ToonBoilerModuleBinarySensor(ToonBinarySensor, ToonBoilerModuleDeviceEntity):
    """Defines a Boiler module binary sensor."""


# pylint: disable=wrong-import-position
# Necessary to prevent circular import
from .entity_descriptions import (  # noqa: E402
    BINARY_SENSOR_ENTITIES,
    BINARY_SENSOR_ENTITIES_BOILER,
    ToonBinarySensorEntityDescription,
)
