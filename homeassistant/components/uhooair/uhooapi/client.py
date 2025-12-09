"""imports for client.py."""

import logging

from aiohttp import ClientSession

from ..const import APP_VERSION, LOGGER
from .api import API
from .device import Device
from .errors import ForbiddenError, UnauthorizedError
from .util import json_pp


class Client:
    """Client layer for Uhoo API."""

    def __init__(self, api_key: str, websession: ClientSession, **kwargs) -> None:
        """Initialize Client."""
        self._log: logging.Logger = LOGGER

        if kwargs.get("debug") is True:
            self._log.setLevel(logging.DEBUG)
            self._log.debug("Debug mode is explicitly enabled.")
        else:
            self._log.debug(
                "Debug mode is not explicitly enabled (but may be enabled elsewhere)."
            )

        self._app_version: int = APP_VERSION
        self._api_key: str = api_key
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._websession: ClientSession = websession
        self._mac_address: str | None = None
        self._serial_number: str | None = None
        self._mode: str = "minute"
        self._limit: int = 5
        self.devices: dict[str, Device] = {}

        self._api: API = API(self._websession)

    async def login(self) -> None:
        """Login API calls to Uhoo."""
        user_token: dict | None = await self._api.generate_token(self._api_key)
        self._log.debug(f"[generate_token] returned\n{json_pp(user_token)}")
        if user_token is not None:
            self._access_token = user_token["access_token"]
            self._refresh_token = user_token["refresh_token"]
        self._api.set_bearer_token(self._access_token)

    async def setup_devices(self) -> None:
        """Setup devices for the account."""
        device_list: list | None = None
        try:
            device_list = await self._api.get_device_list()
        except (UnauthorizedError, ForbiddenError) as err:
            self._log.debug(
                f"[setup_devices] received {type(err).__name__}, refreshing token and trying again"
            )
            await self.login()
            device_list = await self._api.get_device_list()

        device: dict
        if device_list is not None:
            for device in device_list:
                serial_number: str = device["serialNumber"]
                if serial_number not in self.devices:
                    self.devices[serial_number] = Device(device)

    async def get_latest_data(self, serial_number: str) -> None:
        """Get latest data for all of the devices."""
        try:
            data_latest: dict | None = await self._api.get_device_data(
                serial_number, self._mode, self._limit
            )
        except UnauthorizedError:
            self._log.debug(
                "[get_latest_data] received 401 error, refreshing token and trying again"
            )
            await self.login()
            data_latest = await self._api.get_device_data(
                serial_number, self._mode, self._limit
            )
        except ForbiddenError:
            self._log.debug(
                "[get_latest_data] received 403 error, refreshing token and trying again"
            )
            await self.login()
            data_latest = await self._api.get_device_data(
                serial_number, self._mode, self._limit
            )

        if serial_number not in self.devices:
            LOGGER.error(
                "[client get_latest_data], no serial number saved to setup devices"
            )
        if data_latest is not None:
            data: list = data_latest["data"]
        device_obj: Device = self.devices[serial_number]
        device_obj.update_data(data)

    def get_devices(self) -> dict[str, Device]:
        """Get the device list."""
        return self.devices
