"""Code to handle a Xiaomi Device."""

import datetime
from enum import Enum
from functools import partial
import logging
from typing import TYPE_CHECKING, Any

from miio import Device as MiioDevice, DeviceException
from miio.gateway.devices import SubDevice

from homeassistant.const import ATTR_CONNECTIONS, CONF_MAC, CONF_MODEL
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTR_AVAILABLE, DOMAIN
from .typing import XiaomiMiioConfigEntry

_LOGGER = logging.getLogger(__name__)


class XiaomiMiioEntity(Entity):
    """Representation of a base Xiaomi Miio Entity."""

    def __init__(
        self,
        name: str,
        device: MiioDevice,
        entry: XiaomiMiioConfigEntry,
        unique_id: str | None,
    ) -> None:
        """Initialize the Xiaomi Miio Device."""
        self._device = device
        self._model = entry.data[CONF_MODEL]
        self._mac = entry.data[CONF_MAC]
        self._device_id = entry.unique_id
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_available = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        if TYPE_CHECKING:
            assert self._device_id is not None
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Xiaomi",
            model=self._model,
            name=self._attr_name,
        )

        if self._mac is not None:
            device_info[ATTR_CONNECTIONS] = {(dr.CONNECTION_NETWORK_MAC, self._mac)}

        return device_info


class XiaomiCoordinatedMiioEntity[_T: DataUpdateCoordinator[Any]](
    CoordinatorEntity[_T]
):
    """Representation of a base a coordinated Xiaomi Miio Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: MiioDevice,
        entry: XiaomiMiioConfigEntry,
        unique_id: str | None,
        coordinator: _T,
    ) -> None:
        """Initialize the coordinated Xiaomi Miio Device."""
        super().__init__(coordinator)
        self._device = device
        self._model = entry.data[CONF_MODEL]
        self._mac = entry.data[CONF_MAC]
        self._device_id = entry.unique_id
        self._device_name = entry.title
        self._attr_unique_id = unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        if TYPE_CHECKING:
            assert self._device_id is not None
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
        except DeviceException as exc:
            if self.available:
                _LOGGER.error(mask_error, exc)

            return False

        _LOGGER.debug("Response received from miio device: %s", result)
        return True

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
    def _parse_datetime_time(initial_time: datetime.time) -> str:
        time = datetime.datetime.now().replace(
            hour=initial_time.hour, minute=initial_time.minute, second=0, microsecond=0
        )

        if time < datetime.datetime.now():
            time += datetime.timedelta(days=1)

        return time.isoformat()

    @staticmethod
    def _parse_datetime_datetime(time: datetime.datetime) -> str:
        return time.isoformat()


class XiaomiGatewayDevice(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, bool]]], Entity
):
    """Representation of a base Xiaomi Gateway Device."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, bool]],
        sub_device: SubDevice,
        entry: XiaomiMiioConfigEntry,
    ) -> None:
        """Initialize the Xiaomi Gateway Device."""
        super().__init__(coordinator)
        self._sub_device = sub_device
        self._entry = entry
        self._attr_unique_id = sub_device.sid
        self._attr_name = f"{sub_device.name} ({sub_device.sid})"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info of the gateway."""
        if TYPE_CHECKING:
            assert self._entry.unique_id is not None
        return DeviceInfo(
            identifiers={(DOMAIN, self._sub_device.sid)},
            via_device=(DOMAIN, self._entry.unique_id),
            manufacturer="Xiaomi",
            name=self._sub_device.name,
            model=self._sub_device.model,
            sw_version=self._sub_device.firmware_version,
            hw_version=self._sub_device.zigbee_model,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self.coordinator.data is None:
            return False

        return self.coordinator.data[ATTR_AVAILABLE]
