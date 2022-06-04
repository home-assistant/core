"""Coordinator to fetch data from SAJ solar inverter."""
import asyncio
import logging
from urllib.parse import urlparse

import pysaj

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_NAME, DOMAIN, INVERTER_TYPES, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


def _init_pysaj(wifi, host, username, password):  # pragma: no cover
    kwargs = {"wifi": wifi}
    if username and password:
        kwargs["username"] = username
        kwargs["password"] = password

    return pysaj.SAJ(host, **kwargs)


class SAJDataUpdateCoordinator(DataUpdateCoordinator):
    """Representation of a SAJ inverter."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
    ) -> None:
        """Init SAJ Inverter class."""
        super().__init__(
            hass,
            _LOGGER,
            name=config[CONF_NAME] or DEFAULT_NAME,
            update_interval=UPDATE_INTERVAL,
            update_method=self.update,
        )
        self.last_update_success = False
        wifi = config[CONF_TYPE] == INVERTER_TYPES[1]
        self._saj = _init_pysaj(
            wifi, config[CONF_HOST], config[CONF_USERNAME], config[CONF_PASSWORD]
        )
        self._sensor_def = pysaj.Sensors(wifi)

    def get_enabled_sensors(self):
        """Return enabled sensors."""
        return [s for s in self._sensor_def if s.enabled]

    @property
    def serialnumber(self):
        """Return the serial number of the inverter."""
        return self._saj.serialnumber

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        url = urlparse(self._saj.url)._replace(path="/").geturl()
        return DeviceInfo(
            identifiers={(DOMAIN, self._saj.serialnumber)},
            manufacturer="SAJ",
            name=self.name,
            configuration_url=url,
        )

    async def connect(self):
        """Try to connect to the inverter."""
        try:
            success = await self._saj.read(self._sensor_def)
        except asyncio.TimeoutError as err:
            raise CannotConnect from err
        if not success:
            raise CannotConnect

    async def update(self):
        """Fetch data from Inverter."""
        done = await self._saj.read(self._sensor_def)
        if done:
            return self._sensor_def

        raise UpdateFailed


class CannotConnect(ConfigEntryNotReady):
    """Error to indicate we cannot connect."""
