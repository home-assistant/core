"""Base AndroidTV Entity."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
import functools
import logging
from typing import Any, Concatenate

from androidtv.exceptions import LockNotAcquiredException
from androidtvremote2 import AndroidTVRemote, ConnectionClosed

from homeassistant.const import (
    ATTR_CONNECTIONS,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SW_VERSION,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity

from . import (
    ADB_PYTHON_EXCEPTIONS,
    ADB_TCP_EXCEPTIONS,
    AndroidTVADBRuntimeData,
    AndroidTVConfigEntry,
    AndroidTVRemoteRuntimeData,
    get_androidtv_mac,
)
from .const import CONF_APPS, DEVICE_ANDROIDTV, DOMAIN

PREFIX_ANDROIDTV = "Android TV"
PREFIX_FIRETV = "Fire TV"

_LOGGER = logging.getLogger(__name__)

type _FuncType[_T, **_P, _R] = Callable[Concatenate[_T, _P], Awaitable[_R]]
type _ReturnFuncType[_T, **_P, _R] = Callable[
    Concatenate[_T, _P], Coroutine[Any, Any, _R | None]
]


def adb_decorator[_ADBDeviceT: AndroidTVADBEntity, **_P, _R](
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


class AndroidTVADBEntity(Entity):
    """Defines a base AndroidTV entity for ADB connection."""

    _attr_has_entity_name = True

    def __init__(self, entry: AndroidTVConfigEntry) -> None:
        """Initialize the AndroidTV base entity."""
        runtime_data = entry.runtime_data
        assert isinstance(runtime_data, AndroidTVADBRuntimeData)
        self.aftv = runtime_data.aftv
        self._attr_unique_id = entry.unique_id
        self._entry_runtime_data = runtime_data

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
            # Communicate via ADB server
            self.exceptions = ADB_TCP_EXCEPTIONS


class AndroidTVRemoteEntity(Entity):
    """Android TV Remote Base Entity for Remote protocol connection."""

    _attr_name = None
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, api: AndroidTVRemote, config_entry: AndroidTVConfigEntry
    ) -> None:
        """Initialize the entity."""
        self._api = api
        self._apps: dict[str, Any] = config_entry.options.get(CONF_APPS, {})
        self._attr_unique_id = config_entry.unique_id
        self._attr_is_on = api.is_on
        device_info = api.device_info
        assert config_entry.unique_id
        assert device_info
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, config_entry.data[CONF_MAC])},
            identifiers={(DOMAIN, config_entry.unique_id)},
            name=config_entry.data[CONF_NAME],
            manufacturer=device_info["manufacturer"],
            model=device_info["model"],
        )

    @callback
    def _is_available_updated(self, is_available: bool) -> None:
        """Update the state when the device is ready to receive commands or is unavailable."""
        self._attr_available = is_available
        self.async_write_ha_state()

    @callback
    def _is_on_updated(self, is_on: bool) -> None:
        """Update the state when device turns on or off."""
        self._attr_is_on = is_on
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._api.add_is_available_updated_callback(self._is_available_updated)
        self._api.add_is_on_updated_callback(self._is_on_updated)

    async def async_will_remove_from_hass(self) -> None:
        """Remove callbacks."""
        self._api.remove_is_available_updated_callback(self._is_available_updated)
        self._api.remove_is_on_updated_callback(self._is_on_updated)

    def _send_key_command(self, key_code: str, direction: str = "SHORT") -> None:
        """Send a key press to Android TV.

        This does not block; it buffers the data and arranges for it to be sent out asynchronously.
        """
        try:
            self._api.send_key_command(key_code, direction)
        except ConnectionClosed as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="connection_closed"
            ) from exc

    def _send_launch_app_command(self, app_link: str) -> None:
        """Launch an app on Android TV.

        This does not block; it buffers the data and arranges for it to be sent out asynchronously.
        """
        try:
            self._api.send_launch_app_command(app_link)
        except ConnectionClosed as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="connection_closed"
            ) from exc


# Backwards compatibility alias
AndroidTVEntity = AndroidTVADBEntity
