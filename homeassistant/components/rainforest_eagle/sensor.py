"""Support for the Rainforest Eagle-200 energy monitor."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASS_ENERGY,
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
    StateType,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CLOUD_ID, CONF_INSTALL_CODE, DOMAIN
from .data import EagleDataCoordinator

_LOGGER = logging.getLogger(__name__)

POWER_KILO_WATT = "kW"

SENSORS = (
    SensorEntityDescription(
        key="instantanous_demand",
        name="Meter Power Demand",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    SensorEntityDescription(
        key="summation_delivered",
        name="Total Meter Energy Delivered",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="summation_received",
        name="Total Meter Energy Received",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="summation_total",
        name="Net Meter Energy (Delivered minus Received)",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_CLOUD_ID): cv.string,
        vol.Required(CONF_INSTALL_CODE): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
):
    """Import config as config entry."""
    _LOGGER.warning(
        "Configuration of the EAGLE-200 platform in YAML is deprecated and will be "
        "removed in Home Assistant 2021.11; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_CLOUD_ID: config[CONF_CLOUD_ID],
                CONF_INSTALL_CODE: config[CONF_INSTALL_CODE],
            },
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(EagleSensor(coordinator, description) for description in SENSORS)


class EagleSensor(CoordinatorEntity, SensorEntity):
    """Implementation of the Rainforest Eagle-200 sensor."""

    coordinator: EagleDataCoordinator

    def __init__(self, coordinator, entity_description):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description

    @property
    def unique_id(self) -> str | None:
        """Return unique ID of entity."""
        return f"{self.coordinator.cloud_id}-{self.entity_description.key}"

    @property
    def native_value(self) -> StateType:
        """Return native value of the sensor."""
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info."""
        return {
            "name": "EAGLE-200",
            "identifiers": {(DOMAIN, self.coordinator.cloud_id)},
            "manufacturer": "Rainforest Automation",
            "model": "EAGLE-200",
        }
