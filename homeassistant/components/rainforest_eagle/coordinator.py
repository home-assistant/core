"""Rainforest data."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import aioeagle
from eagle100 import Eagle as Eagle100Reader

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CLOUD_ID,
    CONF_HARDWARE_ADDRESS,
    CONF_INSTALL_CODE,
    TYPE_EAGLE_100,
)
from .data import UPDATE_100_ERRORS

_LOGGER = logging.getLogger(__name__)


class EagleDataCoordinator(DataUpdateCoordinator):
    """Get the latest data from the Eagle device."""

    eagle100_reader: Eagle100Reader | None = None
    eagle200_meter: aioeagle.ElectricMeter | None = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the data object."""
        self.entry = entry
        if self.type == TYPE_EAGLE_100:
            self.model = "EAGLE-100"
            update_method = self._async_update_data_100
        else:
            self.model = "EAGLE-200"
            update_method = self._async_update_data_200

        super().__init__(
            hass,
            _LOGGER,
            name=entry.data[CONF_CLOUD_ID],
            update_interval=timedelta(seconds=30),
            update_method=update_method,
        )

    @property
    def cloud_id(self):
        """Return the cloud ID."""
        return self.entry.data[CONF_CLOUD_ID]

    @property
    def type(self):
        """Return entry type."""
        return self.entry.data[CONF_TYPE]

    @property
    def hardware_address(self):
        """Return hardware address of meter."""
        return self.entry.data[CONF_HARDWARE_ADDRESS]

    @property
    def is_connected(self):
        """Return if the hub is connected to the electric meter."""
        if self.eagle200_meter:
            return self.eagle200_meter.is_connected

        return True

    async def _async_update_data_200(self):
        """Get the latest data from the Eagle-200 device."""
        if (eagle200_meter := self.eagle200_meter) is None:
            hub = aioeagle.EagleHub(
                aiohttp_client.async_get_clientsession(self.hass),
                self.cloud_id,
                self.entry.data[CONF_INSTALL_CODE],
                host=self.entry.data[CONF_HOST],
            )
            eagle200_meter = aioeagle.ElectricMeter.create_instance(
                hub, self.hardware_address
            )
            is_connected = True
        else:
            is_connected = eagle200_meter.is_connected

        async with asyncio.timeout(30):
            data = await eagle200_meter.get_device_query()

        if self.eagle200_meter is None:
            self.eagle200_meter = eagle200_meter
        elif is_connected and not eagle200_meter.is_connected:
            _LOGGER.warning("Lost connection with electricity meter")

        _LOGGER.debug("API data: %s", data)
        return {var["Name"]: var["Value"] for var in data.values()}

    async def _async_update_data_100(self):
        """Get the latest data from the Eagle-100 device."""
        try:
            data = await self.hass.async_add_executor_job(self._fetch_data_100)
        except UPDATE_100_ERRORS as error:
            raise UpdateFailed from error

        _LOGGER.debug("API data: %s", data)
        return data

    def _fetch_data_100(self):
        """Fetch and return the four sensor values in a dict."""
        if self.eagle100_reader is None:
            self.eagle100_reader = Eagle100Reader(
                self.cloud_id,
                self.entry.data[CONF_INSTALL_CODE],
                self.entry.data[CONF_HOST],
            )

        out = {}

        resp = self.eagle100_reader.get_instantaneous_demand()["InstantaneousDemand"]
        out["zigbee:InstantaneousDemand"] = resp["Demand"]

        resp = self.eagle100_reader.get_current_summation()["CurrentSummation"]
        out["zigbee:CurrentSummationDelivered"] = resp["SummationDelivered"]
        out["zigbee:CurrentSummationReceived"] = resp["SummationReceived"]

        return out
