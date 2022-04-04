"""Code to handle a Xiaomi Device."""
import datetime
from enum import Enum
from functools import partial
import logging
from typing import Any, TypeVar

from construct.core import ChecksumError
from miio import Device, DeviceException

from homeassistant.const import ATTR_CONNECTIONS, CONF_MODEL
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_MAC, DOMAIN, AuthException, SetupException

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T", bound=DataUpdateCoordinator[Any])


class ConnectXiaomiDevice:
    """Class to async connect to a Xiaomi Device."""

    def __init__(self, hass):
        """Initialize the entity."""
        self._hass = hass
        self._device = None
        self._device_info = None

    @property
    def device(self):
        """Return the class containing all connections to the device."""
        return self._device

    @property
    def device_info(self):
        """Return the class containing device info."""
        return self._device_info

    async def async_connect_device(self, host, token):
        """Connect to the Xiaomi Device."""
        _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

        try:
            self._device = Device(host, token)
            # get the device info
            self._device_info = await self._hass.async_add_executor_job(
                self._device.info
            )
        except DeviceException as error:
            if isinstance(error.__cause__, ChecksumError):
                raise AuthException(error) from error

            raise SetupException(
                f"DeviceException during setup of xiaomi device with host {host}"
            ) from error

        _LOGGER.debug(
            "%s %s %s detected",
            self._device_info.model,
            self._device_info.firmware_version,
            self._device_info.hardware_version,
        )


class XiaomiMiioEntity(Entity):
    """Representation of a base Xiaomi Miio Entity."""

    def __init__(self, name, device, entry, unique_id):
        """Initialize the Xiaomi Miio Device."""
        self._device = device
        self._model = entry.data[CONF_MODEL]
        self._mac = entry.data[CONF_MAC]
        self._device_id = entry.unique_id
        self._unique_id = unique_id
        self._name = name
        self._available = None

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Xiaomi",
            model=self._model,
            name=self._name,
        )

        if self._mac is not None:
            device_info[ATTR_CONNECTIONS] = {(dr.CONNECTION_NETWORK_MAC, self._mac)}

        return device_info


class XiaomiCoordinatedMiioEntity(CoordinatorEntity[_T]):
    """Representation of a base a coordinated Xiaomi Miio Entity."""

    def __init__(self, name, device, entry, unique_id, coordinator):
        """Initialize the coordinated Xiaomi Miio Device."""
        super().__init__(coordinator)
        self._device = device
        self._model = entry.data[CONF_MODEL]
        self._mac = entry.data[CONF_MAC]
        self._device_id = entry.unique_id
        self._device_name = entry.title
        self._unique_id = unique_id
        self._name = name

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Xiaomi",
            model=self._model,
            name=self._device_name,
        )

        if self._mac is not None:
            device_info[ATTR_CONNECTIONS] = {(dr.CONNECTION_NETWORK_MAC, self._mac)}

        return device_info

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a miio device command handling error messages."""
        try:
            result = await self.hass.async_add_executor_job(
                partial(func, *args, **kwargs)
            )

            _LOGGER.debug("Response received from miio device: %s", result)

            return True
        except DeviceException as exc:
            if self.available:
                _LOGGER.error(mask_error, exc)

            return False

    @classmethod
    def _extract_value_from_attribute(cls, state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime.timedelta):
            return cls._parse_time_delta(value)
        if isinstance(value, datetime.time):
            return cls._parse_datetime_time(value)
        if isinstance(value, datetime.datetime):
            return cls._parse_datetime_datetime(value)

        if value is None:
            _LOGGER.debug("Attribute %s is None, this is unexpected", attribute)

        return value

    @staticmethod
    def _parse_time_delta(timedelta: datetime.timedelta) -> int:
        return int(timedelta.total_seconds())

    @staticmethod
    def _parse_datetime_time(time: datetime.time) -> str:
        time = datetime.datetime.now().replace(
            hour=time.hour, minute=time.minute, second=0, microsecond=0
        )

        if time < datetime.datetime.now():
            time += datetime.timedelta(days=1)

        return time.isoformat()

    @staticmethod
    def _parse_datetime_datetime(time: datetime.datetime) -> str:
        return time.isoformat()
