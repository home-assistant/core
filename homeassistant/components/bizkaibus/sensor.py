"""Support for Bizkaibus, Biscay (Basque Country, Spain) Bus service."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import BizkaibusConfigEntry, BizkaibusUpdateCoordinator

ATTR_DUE_IN = "Due in"

CONF_STOP_ID = "stopid"
CONF_ROUTE = "route"

DEFAULT_NAME = "Next bus"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOP_ID): cv.string,
        # vol.Optional(CONF_ROUTE): cv.string,
        # vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BizkaibusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bizkaibus public transport sensor."""

    coordinator = config_entry.runtime_data

    async_add_entities([BizkaibusSensor(coordinator)], True)


class BizkaibusSensor(CoordinatorEntity[BizkaibusUpdateCoordinator], SensorEntity):
    """The class for handling the data."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_should_poll = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: BizkaibusUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.api.stop)},
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_unique_id = f"{coordinator.api.stop}_{'asd'}"
        self._attr_name = coordinator.friendly_name
