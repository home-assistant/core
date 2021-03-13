"""Support for Toon binary sensors."""
from typing import Optional

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTR_DEFAULT_ENABLED,
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_INVERTED,
    ATTR_MEASUREMENT,
    ATTR_NAME,
    ATTR_SECTION,
    BINARY_SENSOR_ENTITIES,
    DOMAIN,
)
from .coordinator import ToonDataUpdateCoordinator
from .models import (
    ToonBoilerDeviceEntity,
    ToonBoilerModuleDeviceEntity,
    ToonDisplayDeviceEntity,
    ToonEntity,
)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up a Toon binary sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        ToonBoilerModuleBinarySensor(
            coordinator, key="thermostat_info_boiler_connected_None"
        ),
        ToonDisplayBinarySensor(coordinator, key="thermostat_program_overridden"),
    ]

    if coordinator.data.thermostat.have_opentherm_boiler:
        sensors.extend(
            [
                ToonBoilerBinarySensor(coordinator, key=key)
                for key in [
                    "thermostat_info_ot_communication_error_0",
                    "thermostat_info_error_found_255",
                    "thermostat_info_burner_info_None",
                    "thermostat_info_burner_info_1",
                    "thermostat_info_burner_info_2",
                    "thermostat_info_burner_info_3",
                ]
            ]
        )

    async_add_entities(sensors, True)


class ToonBinarySensor(ToonEntity, BinarySensorEntity):
    """Defines an Toon binary sensor."""

    def __init__(self, coordinator: ToonDataUpdateCoordinator, *, key: str) -> None:
        """Initialize the Toon sensor."""
        self.key = key

        super().__init__(
            coordinator,
            enabled_default=BINARY_SENSOR_ENTITIES[key][ATTR_DEFAULT_ENABLED],
            icon=BINARY_SENSOR_ENTITIES[key][ATTR_ICON],
            name=BINARY_SENSOR_ENTITIES[key][ATTR_NAME],
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this binary sensor."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        # This unique ID is a bit ugly and contains unneeded information.
        # It is here for legacy / backward compatible reasons.
        return f"{DOMAIN}_{agreement_id}_binary_sensor_{self.key}"

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return BINARY_SENSOR_ENTITIES[self.key][ATTR_DEVICE_CLASS]

    @property
    def is_on(self) -> Optional[bool]:
        """Return the status of the binary sensor."""
        section = getattr(
            self.coordinator.data, BINARY_SENSOR_ENTITIES[self.key][ATTR_SECTION]
        )
        value = getattr(section, BINARY_SENSOR_ENTITIES[self.key][ATTR_MEASUREMENT])

        if value is None:
            return None

        if BINARY_SENSOR_ENTITIES[self.key][ATTR_INVERTED]:
            return not value

        return value


class ToonBoilerBinarySensor(ToonBinarySensor, ToonBoilerDeviceEntity):
    """Defines a Boiler binary sensor."""


class ToonDisplayBinarySensor(ToonBinarySensor, ToonDisplayDeviceEntity):
    """Defines a Toon Display binary sensor."""


class ToonBoilerModuleBinarySensor(ToonBinarySensor, ToonBoilerModuleDeviceEntity):
    """Defines a Boiler module binary sensor."""
