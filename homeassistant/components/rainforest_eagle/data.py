"""Rainforest data."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import aioeagle
import aiohttp
from eagle100 import Eagle as Eagle100Reader
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CLOUD_ID,
    CONF_HARDWARE_ADDRESS,
    CONF_INSTALL_CODE,
    TYPE_EAGLE_100,
    TYPE_EAGLE_200,
)

_LOGGER = logging.getLogger(__name__)

UPDATE_100_ERRORS = (ConnectError, HTTPError, Timeout)


class RainforestError(HomeAssistantError):
    """Base error."""


class CannotConnect(RainforestError):
    """Error to indicate a request failed."""


class InvalidAuth(RainforestError):
    """Error to indicate bad auth."""


async def async_get_type(hass, cloud_id, install_code, host):
    """Try API call 'get_network_info' to see if target device is Eagle-100 or Eagle-200."""
    # For EAGLE-200, fetch the hardware address of the meter too.
    hub = aioeagle.EagleHub(
        aiohttp_client.async_get_clientsession(hass), cloud_id, install_code, host=host
    )

    try:
        async with asyncio.timeout(30):
            meters = await hub.get_device_list()
    except aioeagle.BadAuth as err:
        raise InvalidAuth from err
    except (KeyError, aiohttp.ClientError):
        # This can happen if it's an eagle-100
        meters = None

    if meters is not None:
        if meters:
            hardware_address = meters[0].hardware_address
        else:
            hardware_address = None

        return TYPE_EAGLE_200, hardware_address

    reader = Eagle100Reader(cloud_id, install_code, host)

    try:
        response = await hass.async_add_executor_job(reader.get_network_info)
    except ValueError as err:
        # This could be invalid auth because it doesn't check 401 and tries to read JSON.
        raise InvalidAuth from err
    except UPDATE_100_ERRORS as error:
        _LOGGER.error("Failed to connect during setup: %s", error)
        raise CannotConnect from error

    # Branch to test if target is Legacy Model
    if (
        "NetworkInfo" in response
        and response["NetworkInfo"].get("ModelId") == "Z109-EAGLE"
    ):
        return TYPE_EAGLE_100, None

    return None, None


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
