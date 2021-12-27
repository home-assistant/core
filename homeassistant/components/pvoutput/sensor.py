"""Support for getting collected information from PVOutput."""
from __future__ import annotations

from pvo import Status
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    CONF_API_KEY,
    CONF_NAME,
    ENERGY_WATT_HOUR,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    ATTR_EFFICIENCY,
    ATTR_ENERGY_CONSUMPTION,
    ATTR_ENERGY_GENERATION,
    ATTR_POWER_CONSUMPTION,
    ATTR_POWER_GENERATION,
    CONF_SYSTEM_ID,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_SYSTEM_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the PVOutput sensor."""
    LOGGER.warning(
        "Configuration of the PVOutput platform in YAML is deprecated and will be "
        "removed in Home Assistant 2022.4; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_SYSTEM_ID: config[CONF_SYSTEM_ID],
                CONF_API_KEY: config[CONF_API_KEY],
                CONF_NAME: config[CONF_NAME],
            },
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Tailscale binary sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PvoutputSensor(coordinator)])


class PvoutputSensor(CoordinatorEntity, SensorEntity):
    """Representation of a PVOutput sensor."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = ENERGY_WATT_HOUR

    coordinator: DataUpdateCoordinator[Status]

    @property
    def native_value(self) -> int | None:
        """Return the state of the device."""
        return self.coordinator.data.energy_generation

    @property
    def extra_state_attributes(self) -> dict[str, int | float | None]:
        """Return the state attributes of the monitored installation."""
        return {
            ATTR_ENERGY_GENERATION: self.coordinator.data.energy_generation,
            ATTR_POWER_GENERATION: self.coordinator.data.power_generation,
            ATTR_ENERGY_CONSUMPTION: self.coordinator.data.energy_consumption,
            ATTR_POWER_CONSUMPTION: self.coordinator.data.power_consumption,
            ATTR_EFFICIENCY: self.coordinator.data.normalized_ouput,
            ATTR_TEMPERATURE: self.coordinator.data.temperature,
            ATTR_VOLTAGE: self.coordinator.data.voltage,
        }
