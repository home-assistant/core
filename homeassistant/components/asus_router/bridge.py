"""Asus Router bridge module - handles all the communications with backend library."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import Any

import aiohttp
from asusrouter import AsusDevice, AsusRouter, AsusRouterError

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import helpers
from .const import (
    CONF_DEFAULT_PORT,
    CPU,
    DEFAULT_SENSORS,
    METHOD,
    RAM,
    SENSORS,
    SENSORS_CPU,
    SENSORS_RAM,
)

_LOGGER = logging.getLogger(__name__)


class ARBridge:
    """Bridge to the AsusRouter library."""

    def __init__(
        self,
        hass: HomeAssistant,
        configs: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> None:
        """Initialize bridge to the library."""

        self.hass = hass

        # Save all the HA configs and options
        self._configs = configs.copy()
        if options:
            self._configs.update(options)

        # Get session from HA
        session = async_get_clientsession(hass)

        # Initialize API
        self._api = self._get_api(self._configs, session)

        self._host = self._configs[CONF_HOST]
        self._identity: AsusDevice | None = None

        self._active: bool = False

    @staticmethod
    def _get_api(configs: dict[str, Any], session: aiohttp.ClientSession) -> AsusRouter:
        """Get AsusRouter API."""

        return AsusRouter(
            host=configs[CONF_HOST],
            username=configs[CONF_USERNAME],
            password=configs[CONF_PASSWORD],
            port=configs.get(CONF_PORT, CONF_DEFAULT_PORT),
            use_ssl=configs[CONF_SSL],
            session=session,
        )

    @property
    def active(self) -> bool:
        """Return activity state of the bridge."""

        return self._active

    @property
    def api(self) -> AsusRouter:
        """Return API."""

        return self._api

    @property
    def connected(self) -> bool:
        """Return connection state."""

        return self.api.connected

    @property
    def identity(self) -> AsusDevice:
        """Return device identity."""

        return self._identity

    # CONNECTION ->
    async def async_connect(self) -> None:
        """Connect to the device."""

        await self.api.async_connect()
        self._identity = await self.api.async_get_identity()
        self._active = True

    async def async_disconnect(self) -> None:
        """Disconnect from the device."""

        await self.api.async_disconnect()
        self._active = False

    async def async_clean(self) -> None:
        """Cleanup."""

        await self.api.connection.async_cleanup()

    # <-- CONNECTION

    async def async_get_available_sensors(self) -> dict[str, dict[str, Any]]:
        """Get the list of available sensors."""

        sensors = {
            CPU: {
                SENSORS: await self._get_sensors_cpu(),
                METHOD: self._get_data_cpu,
            },
            RAM: {
                SENSORS: SENSORS_RAM,
                METHOD: self._get_data_ram,
            },
        }

        return sensors

    # GET DATA FROM DEVICE ->
    async def _get_data(
        self,
        method: Callable[[], Awaitable[dict[str, Any]]],
        process: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Get data from the device. This is a generic method."""

        try:
            raw = await method()
            if process is not None:
                return process(raw)
            return self._process_data(raw)
        except AsusRouterError as ex:
            raise UpdateFailed(ex) from ex

    async def _get_data_cpu(self) -> dict[str, Any]:
        """Get CPU data from the device."""

        return await self._get_data(self.api.async_get_cpu)

    async def _get_data_ram(self) -> dict[str, Any]:
        """Get CPU data from the device."""

        return await self._get_data(self.api.async_get_ram)

    # <- GET DATA FROM DEVICE

    # PROCESS DATA ->
    @staticmethod
    def _process_data(raw: dict[str, Any]) -> dict[str, Any]:
        """Process data received from the device. This is a generic method."""

        return helpers.as_dict(helpers.flatten_dict(raw))

    # <- PROCESS DATA

    # GET SENSORS LIST ->
    async def _get_sensors(
        self,
        method: Callable[[], Awaitable[dict[str, Any]]],
        process: Callable[[dict[str, Any]], list[str]] | None = None,
        sensor_type: str | None = None,
        defaults: bool = False,
    ) -> list[str]:
        """Get the available sensors. This is a generic method."""

        sensors = []
        try:
            data = await method()
            sensors = (
                process(data) if process is not None else self._process_sensors(data)
            )
            _LOGGER.debug("Available `%s` sensors: %s", sensor_type, sensors)
        except AsusRouterError as ex:
            if sensor_type in DEFAULT_SENSORS and defaults:
                sensors = DEFAULT_SENSORS[sensor_type]
            _LOGGER.debug(
                "Cannot get available `%s` sensors with exception: %s. \
                    Will use the following list: {sensors}",
                sensor_type,
                ex,
            )
        return sensors

    async def _get_sensors_cpu(self) -> list[str]:
        """Get the available CPU sensors."""

        return await self._get_sensors(
            self.api.async_get_cpu,
            self._process_sensors_cpu,
            sensor_type=CPU,
            defaults=True,
        )

    async def _get_sensors_ram(self) -> list[str]:
        """Get the available RAM sensors."""

        return await self._get_sensors(
            self.api.async_get_ram,
            sensor_type=CPU,
            defaults=True,
        )

    # <- GET SENSORS LIST

    # PROCESS SENSORS LIST->
    @staticmethod
    def _process_sensors(raw: dict[str, Any]) -> list[str]:
        """Process sensors from the backend library. This is a generic method.

        For the most of sensors which are returned as nested dicts
        and only the top level keys are the one we are looking for.
        """

        flat = helpers.as_dict(helpers.flatten_dict(raw))
        return helpers.list_from_dict(flat)

    @staticmethod
    def _process_sensors_cpu(raw: dict[str, Any]) -> list[str]:
        """Process CPU sensors."""

        sensors = []
        for label in raw:
            for sensor in SENSORS_CPU:
                sensors.append(f"{label}_{sensor}")

        return sensors
