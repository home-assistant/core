"""Support for Toon sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ToonDataUpdateCoordinator
from .models import (
    ToonBoilerDeviceEntity,
    ToonDisplayDeviceEntity,
    ToonElectricityMeterDeviceEntity,
    ToonEntity,
    ToonGasMeterDeviceEntity,
    ToonSolarDeviceEntity,
    ToonWaterMeterDeviceEntity,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Toon sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        description.cls(coordinator, description) for description in SENSOR_ENTITIES
    ]

    if coordinator.data.agreement.is_toon_solar:
        entities.extend(
            [
                description.cls(coordinator, description)
                for description in SENSOR_ENTITIES_SOLAR
            ]
        )

    if coordinator.data.thermostat.have_opentherm_boiler:
        entities.extend(
            [
                description.cls(coordinator, description)
                for description in SENSOR_ENTITIES_BOILER
            ]
        )

    async_add_entities(entities, True)


class ToonSensor(ToonEntity, SensorEntity):
    """Defines a Toon sensor."""

    entity_description: ToonSensorEntityDescription

    def __init__(
        self,
        coordinator: ToonDataUpdateCoordinator,
        description: ToonSensorEntityDescription,
    ) -> None:
        """Initialize the Toon sensor."""
        self.entity_description = description
        super().__init__(coordinator)

        self._attr_unique_id = (
            # This unique ID is a bit ugly and contains unneeded information.
            # It is here for legacy / backward compatible reasons.
            f"{DOMAIN}_{coordinator.data.agreement.agreement_id}_sensor_{description.key}"
        )

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        section = getattr(self.coordinator.data, self.entity_description.section)
        return getattr(section, self.entity_description.measurement)


class ToonElectricityMeterDeviceSensor(ToonSensor, ToonElectricityMeterDeviceEntity):
    """Defines a Electricity Meter sensor."""


class ToonGasMeterDeviceSensor(ToonSensor, ToonGasMeterDeviceEntity):
    """Defines a Gas Meter sensor."""


class ToonWaterMeterDeviceSensor(ToonSensor, ToonWaterMeterDeviceEntity):
    """Defines a Water Meter sensor."""


class ToonSolarDeviceSensor(ToonSensor, ToonSolarDeviceEntity):
    """Defines a Solar sensor."""


class ToonBoilerDeviceSensor(ToonSensor, ToonBoilerDeviceEntity):
    """Defines a Boiler sensor."""


class ToonDisplayDeviceSensor(ToonSensor, ToonDisplayDeviceEntity):
    """Defines a Display sensor."""


# pylint: disable=wrong-import-position
# Necessary to prevent circular import
from .entity_descriptions import (  # noqa: E402
    SENSOR_ENTITIES,
    SENSOR_ENTITIES_BOILER,
    SENSOR_ENTITIES_SOLAR,
    ToonSensorEntityDescription,
)
