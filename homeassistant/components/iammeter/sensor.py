"""Support for iammeter via local API."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import async_timeout
from iammeter.client import IamMeter
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import debounce, update_coordinator
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DEVICE_3080,
    DEVICE_3080T,
    DOMAIN,
    SENSOR_TYPES_3080,
    SENSOR_TYPES_3080T,
    IammeterSensorEntityDescription,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 80
DEFAULT_DEVICE_NAME = "IamMeter"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_DEVICE_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

SCAN_INTERVAL = timedelta(seconds=30)
PLATFORM_TIMEOUT = 8


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Platform setup."""
    config_host = config[CONF_HOST]
    config_port = config[CONF_PORT]
    config_name = config[CONF_NAME]
    try:
        api = await hass.async_add_executor_job(
            IamMeter, config_host, config_port, config_name
        )
    except asyncio.TimeoutError as err:
        _LOGGER.error("Device is not ready")
        raise PlatformNotReady from err

    async def async_update_data():
        try:
            async with async_timeout.timeout(PLATFORM_TIMEOUT):
                return await hass.async_add_executor_job(api.client.get_data)
        except asyncio.TimeoutError as err:
            raise UpdateFailed from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=config_name,
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
        request_refresh_debouncer=debounce.Debouncer(
            hass, _LOGGER, cooldown=0.3, immediate=True
        ),
    )
    await coordinator.async_refresh()
    if coordinator.data["Model"] == DEVICE_3080:
        async_add_entities(
            IammeterSensor(coordinator, description)
            for description in SENSOR_TYPES_3080
        )
    if coordinator.data["Model"] == DEVICE_3080T:
        async_add_entities(
            IammeterSensor(coordinator, description)
            for description in SENSOR_TYPES_3080T
        )


class IammeterSensor(update_coordinator.CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    entity_description: IammeterSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: IammeterSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{coordinator.name} {description.name}"
        self._attr_unique_id = f"{coordinator.data['sn']}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data["sn"])},
            manufacturer="IamMeter",
            name=coordinator.name,
        )

    @property
    def native_value(self):
        """Return the native sensor value."""
        raw_attr = self.coordinator.data.get(self.entity_description.key, None)
        if self.entity_description.value:
            return self.entity_description.value(raw_attr)
        return raw_attr
