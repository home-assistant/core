"""Base AndroidTV Entity."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
import functools
import logging
from typing import Any, Concatenate

from androidtv.exceptions import LockNotAcquiredException

from homeassistant.const import (
    ATTR_CONNECTIONS,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SW_VERSION,
    CONF_HOST,
    CONF_NAME,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity

from . import (
    ADB_PYTHON_EXCEPTIONS,
    ADB_TCP_EXCEPTIONS,
    AndroidTVConfigEntry,
    get_androidtv_mac,
)
from .const import DEVICE_ANDROIDTV, DOMAIN

PREFIX_ANDROIDTV = "Android TV"
PREFIX_FIRETV = "Fire TV"

_LOGGER = logging.getLogger(__name__)

type _FuncType[_T, **_P, _R] = Callable[Concatenate[_T, _P], Awaitable[_R]]
type _ReturnFuncType[_T, **_P, _R] = Callable[
    Concatenate[_T, _P], Coroutine[Any, Any, _R | None]
]


def adb_decorator[_ADBDeviceT: AndroidTVEntity, **_P, _R](
    override_available: bool = False,
) -> Callable[[_FuncType[_ADBDeviceT, _P, _R]], _ReturnFuncType[_ADBDeviceT, _P, _R]]:
    """Wrap ADB methods and catch exceptions.

    Allows for overriding the available status of the ADB connection via the
    `override_available` parameter.
    """

    def _adb_decorator(
        func: _FuncType[_ADBDeviceT, _P, _R],
    ) -> _ReturnFuncType[_ADBDeviceT, _P, _R]:
        """Wrap the provided ADB method and catch exceptions."""

        @functools.wraps(func)
        async def _adb_exception_catcher(
            self: _ADBDeviceT, *args: _P.args, **kwargs: _P.kwargs
        ) -> _R | None:
            """Call an ADB-related method and catch exceptions."""
            if not self.available and not override_available:
                return None

            try:
                return await func(self, *args, **kwargs)
            except LockNotAcquiredException:
                # If the ADB lock could not be acquired, skip this command
                _LOGGER.debug(
                    (
                        "ADB command %s not executed because the connection is"
                        " currently in use"
                    ),
                    func.__name__,
                )
                return None
            except self.exceptions as err:
                if self.available:
                    _LOGGER.error(
                        (
                            "Failed to execute an ADB command. ADB connection re-"
                            "establishing attempt in the next update. Error: %s"
                        ),
                        err,
                    )

                await self.aftv.adb_close()
                self._attr_available = False
                return None
            except ServiceValidationError:
                # Service validation error is thrown because raised by remote services
                raise
            except Exception as err:  # noqa: BLE001
                # An unforeseen exception occurred. Close the ADB connection so that
                # it doesn't happen over and over again.
                if self.available:
                    _LOGGER.error(
                        (
                            "Unexpected exception executing an ADB command. ADB connection"
                            " re-establishing attempt in the next update. Error: %s"
                        ),
                        err,
                    )

                await self.aftv.adb_close()
                self._attr_available = False
                return None

        return _adb_exception_catcher

    return _adb_decorator


class AndroidTVEntity(Entity):
    """Defines a base AndroidTV entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: AndroidTVConfigEntry) -> None:
        """Initialize the AndroidTV base entity."""
        self.aftv = entry.runtime_data.aftv
        self._attr_unique_id = entry.unique_id
        self._entry_runtime_data = entry.runtime_data

        device_class = self.aftv.DEVICE_CLASS
        device_type = (
            PREFIX_ANDROIDTV if device_class == DEVICE_ANDROIDTV else PREFIX_FIRETV
        )
        # CONF_NAME may be present in entry.data for configuration imported from YAML
        device_name = entry.data.get(
            CONF_NAME, f"{device_type} {entry.data[CONF_HOST]}"
        )
        info = self.aftv.device_properties
        model = info.get(ATTR_MODEL)
        self._attr_device_info = DeviceInfo(
            model=f"{model} ({device_type})" if model else device_type,
            name=device_name,
        )
        if self.unique_id:
            self._attr_device_info[ATTR_IDENTIFIERS] = {(DOMAIN, self.unique_id)}
        if manufacturer := info.get(ATTR_MANUFACTURER):
            self._attr_device_info[ATTR_MANUFACTURER] = manufacturer
        if sw_version := info.get(ATTR_SW_VERSION):
            self._attr_device_info[ATTR_SW_VERSION] = sw_version
        if mac := get_androidtv_mac(info):
            self._attr_device_info[ATTR_CONNECTIONS] = {(CONNECTION_NETWORK_MAC, mac)}

        # ADB exceptions to catch
        if not self.aftv.adb_server_ip:
            # Using "adb_shell" (Python ADB implementation)
            self.exceptions = ADB_PYTHON_EXCEPTIONS
        else:
            # Using "pure-python-adb" (communicate with ADB server)
            self.exceptions = ADB_TCP_EXCEPTIONS
