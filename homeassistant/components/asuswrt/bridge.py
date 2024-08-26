"""aioasuswrt and pyasuswrt bridge classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import namedtuple
from collections.abc import Awaitable, Callable, Coroutine
import functools
import logging
from typing import Any, cast

from aioasuswrt.asuswrt import AsusWrt as AsusWrtLegacy
from aiohttp import ClientSession
from pyasuswrt import AsusWrtError, AsusWrtHttp
from pyasuswrt.exceptions import AsusWrtNotAvailableInfoError

from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_REQUIRE_IP,
    CONF_SSH_KEY,
    DEFAULT_DNSMASQ,
    DEFAULT_INTERFACE,
    KEY_METHOD,
    KEY_SENSORS,
    PROTOCOL_HTTP,
    PROTOCOL_HTTPS,
    PROTOCOL_TELNET,
    SENSORS_BYTES,
    SENSORS_LOAD_AVG,
    SENSORS_RATES,
    SENSORS_TEMPERATURES,
    SENSORS_TEMPERATURES_LEGACY,
)

SENSORS_TYPE_BYTES = "sensors_bytes"
SENSORS_TYPE_COUNT = "sensors_count"
SENSORS_TYPE_LOAD_AVG = "sensors_load_avg"
SENSORS_TYPE_RATES = "sensors_rates"
SENSORS_TYPE_TEMPERATURES = "sensors_temperatures"

WrtDevice = namedtuple("WrtDevice", ["ip", "name", "connected_to"])  # noqa: PYI024

_LOGGER = logging.getLogger(__name__)

type _FuncType[_T] = Callable[[_T], Awaitable[list[Any] | tuple[Any] | dict[str, Any]]]
type _ReturnFuncType[_T] = Callable[[_T], Coroutine[Any, Any, dict[str, Any]]]


def handle_errors_and_zip[_AsusWrtBridgeT: AsusWrtBridge](
    exceptions: type[Exception] | tuple[type[Exception], ...], keys: list[str] | None
) -> Callable[[_FuncType[_AsusWrtBridgeT]], _ReturnFuncType[_AsusWrtBridgeT]]:
    """Run library methods and zip results or manage exceptions."""

    def _handle_errors_and_zip(
        func: _FuncType[_AsusWrtBridgeT],
    ) -> _ReturnFuncType[_AsusWrtBridgeT]:
        """Run library methods and zip results or manage exceptions."""

        @functools.wraps(func)
        async def _wrapper(self: _AsusWrtBridgeT) -> dict[str, Any]:
            try:
                data = await func(self)
            except exceptions as exc:
                raise UpdateFailed(exc) from exc

            if keys is None:
                if not isinstance(data, dict):
                    raise UpdateFailed("Received invalid data type")
                return data

            if isinstance(data, dict):
                return dict(zip(keys, list(data.values()), strict=False))
            if not isinstance(data, (list, tuple)):
                raise UpdateFailed("Received invalid data type")
            return dict(zip(keys, data, strict=False))

        return _wrapper

    return _handle_errors_and_zip


class AsusWrtBridge(ABC):
    """The Base Bridge abstract class."""

    @staticmethod
    def get_bridge(
        hass: HomeAssistant, conf: dict[str, Any], options: dict[str, Any] | None = None
    ) -> AsusWrtBridge:
        """Get Bridge instance."""
        if conf[CONF_PROTOCOL] in (PROTOCOL_HTTPS, PROTOCOL_HTTP):
            session = async_get_clientsession(hass)
            return AsusWrtHttpBridge(conf, session)
        return AsusWrtLegacyBridge(conf, options)

    def __init__(self, host: str) -> None:
        """Initialize Bridge."""
        self._host = host
        self._firmware: str | None = None
        self._label_mac: str | None = None
        self._model: str | None = None

    @property
    def host(self) -> str:
        """Return hostname."""
        return self._host

    @property
    def firmware(self) -> str | None:
        """Return firmware information."""
        return self._firmware

    @property
    def label_mac(self) -> str | None:
        """Return label mac information."""
        return self._label_mac

    @property
    def model(self) -> str | None:
        """Return model information."""
        return self._model

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Get connected status."""

    @abstractmethod
    async def async_connect(self) -> None:
        """Connect to the device."""

    @abstractmethod
    async def async_disconnect(self) -> None:
        """Disconnect to the device."""

    @abstractmethod
    async def async_get_connected_devices(self) -> dict[str, WrtDevice]:
        """Get list of connected devices."""

    @abstractmethod
    async def async_get_available_sensors(self) -> dict[str, dict[str, Any]]:
        """Return a dictionary of available sensors for this bridge."""


class AsusWrtLegacyBridge(AsusWrtBridge):
    """The Bridge that use legacy library."""

    def __init__(
        self, conf: dict[str, Any], options: dict[str, Any] | None = None
    ) -> None:
        """Initialize Bridge."""
        super().__init__(conf[CONF_HOST])
        self._protocol: str = conf[CONF_PROTOCOL]
        self._api: AsusWrtLegacy = self._get_api(conf, options)

    @staticmethod
    def _get_api(
        conf: dict[str, Any], options: dict[str, Any] | None = None
    ) -> AsusWrtLegacy:
        """Get the AsusWrtLegacy API."""
        opt = options or {}

        return AsusWrtLegacy(
            conf[CONF_HOST],
            conf.get(CONF_PORT),
            conf[CONF_PROTOCOL] == PROTOCOL_TELNET,
            conf[CONF_USERNAME],
            conf.get(CONF_PASSWORD, ""),
            conf.get(CONF_SSH_KEY, ""),
            conf[CONF_MODE],
            opt.get(CONF_REQUIRE_IP, True),
            interface=opt.get(CONF_INTERFACE, DEFAULT_INTERFACE),
            dnsmasq=opt.get(CONF_DNSMASQ, DEFAULT_DNSMASQ),
        )

    @property
    def is_connected(self) -> bool:
        """Get connected status."""
        return cast(bool, self._api.is_connected)

    async def async_connect(self) -> None:
        """Connect to the device."""
        await self._api.connection.async_connect()

        # get main router properties
        if self._label_mac is None:
            await self._get_label_mac()
        if self._firmware is None:
            await self._get_firmware()
        if self._model is None:
            await self._get_model()

    async def async_disconnect(self) -> None:
        """Disconnect to the device."""
        if self._api is not None and self._protocol == PROTOCOL_TELNET:
            self._api.connection.disconnect()

    async def async_get_connected_devices(self) -> dict[str, WrtDevice]:
        """Get list of connected devices."""
        api_devices = await self._api.async_get_connected_devices()
        return {
            format_mac(mac): WrtDevice(dev.ip, dev.name, None)
            for mac, dev in api_devices.items()
        }

    async def _get_nvram_info(self, info_type: str) -> dict[str, Any]:
        """Get AsusWrt router info from nvram."""
        info = {}
        try:
            info = await self._api.async_get_nvram(info_type)
        except OSError as exc:
            _LOGGER.warning(
                "Error calling method async_get_nvram(%s): %s", info_type, exc
            )

        return info

    async def _get_label_mac(self) -> None:
        """Get label mac information."""
        label_mac = await self._get_nvram_info("LABEL_MAC")
        if label_mac and "label_mac" in label_mac:
            self._label_mac = format_mac(label_mac["label_mac"])

    async def _get_firmware(self) -> None:
        """Get firmware information."""
        firmware = await self._get_nvram_info("FIRMWARE")
        if firmware and "firmver" in firmware:
            firmver: str = firmware["firmver"]
            if "buildno" in firmware:
                firmver += f" (build {firmware['buildno']})"
            self._firmware = firmver

    async def _get_model(self) -> None:
        """Get model information."""
        model = await self._get_nvram_info("MODEL")
        if model and "model" in model:
            self._model = model["model"]

    async def async_get_available_sensors(self) -> dict[str, dict[str, Any]]:
        """Return a dictionary of available sensors for this bridge."""
        sensors_temperatures = await self._get_available_temperature_sensors()
        return {
            SENSORS_TYPE_BYTES: {
                KEY_SENSORS: SENSORS_BYTES,
                KEY_METHOD: self._get_bytes,
            },
            SENSORS_TYPE_LOAD_AVG: {
                KEY_SENSORS: SENSORS_LOAD_AVG,
                KEY_METHOD: self._get_load_avg,
            },
            SENSORS_TYPE_RATES: {
                KEY_SENSORS: SENSORS_RATES,
                KEY_METHOD: self._get_rates,
            },
            SENSORS_TYPE_TEMPERATURES: {
                KEY_SENSORS: sensors_temperatures,
                KEY_METHOD: self._get_temperatures,
            },
        }

    async def _get_available_temperature_sensors(self) -> list[str]:
        """Check which temperature information is available on the router."""
        availability = await self._api.async_find_temperature_commands()
        return [SENSORS_TEMPERATURES_LEGACY[i] for i in range(3) if availability[i]]

    @handle_errors_and_zip((IndexError, OSError, ValueError), SENSORS_BYTES)
    async def _get_bytes(self) -> Any:
        """Fetch byte information from the router."""
        return await self._api.async_get_bytes_total()

    @handle_errors_and_zip((IndexError, OSError, ValueError), SENSORS_RATES)
    async def _get_rates(self) -> Any:
        """Fetch rates information from the router."""
        return await self._api.async_get_current_transfer_rates()

    @handle_errors_and_zip((IndexError, OSError, ValueError), SENSORS_LOAD_AVG)
    async def _get_load_avg(self) -> Any:
        """Fetch load average information from the router."""
        return await self._api.async_get_loadavg()

    @handle_errors_and_zip((OSError, ValueError), None)
    async def _get_temperatures(self) -> Any:
        """Fetch temperatures information from the router."""
        return await self._api.async_get_temperature()


class AsusWrtHttpBridge(AsusWrtBridge):
    """The Bridge that use HTTP library."""

    def __init__(self, conf: dict[str, Any], session: ClientSession) -> None:
        """Initialize Bridge that use HTTP library."""
        super().__init__(conf[CONF_HOST])
        self._api: AsusWrtHttp = self._get_api(conf, session)

    @staticmethod
    def _get_api(conf: dict[str, Any], session: ClientSession) -> AsusWrtHttp:
        """Get the AsusWrtHttp API."""
        return AsusWrtHttp(
            conf[CONF_HOST],
            conf[CONF_USERNAME],
            conf.get(CONF_PASSWORD, ""),
            use_https=conf[CONF_PROTOCOL] == PROTOCOL_HTTPS,
            port=conf.get(CONF_PORT),
            session=session,
        )

    @property
    def is_connected(self) -> bool:
        """Get connected status."""
        return cast(bool, self._api.is_connected)

    async def async_connect(self) -> None:
        """Connect to the device."""
        await self._api.async_connect()

        # get main router properties
        if mac := self._api.mac:
            self._label_mac = format_mac(mac)
        self._firmware = self._api.firmware
        self._model = self._api.model

    async def async_disconnect(self) -> None:
        """Disconnect to the device."""
        await self._api.async_disconnect()

    async def async_get_connected_devices(self) -> dict[str, WrtDevice]:
        """Get list of connected devices."""
        api_devices = await self._api.async_get_connected_devices()
        return {
            format_mac(mac): WrtDevice(dev.ip, dev.name, dev.node)
            for mac, dev in api_devices.items()
        }

    async def async_get_available_sensors(self) -> dict[str, dict[str, Any]]:
        """Return a dictionary of available sensors for this bridge."""
        sensors_temperatures = await self._get_available_temperature_sensors()
        sensors_loadavg = await self._get_loadavg_sensors_availability()
        return {
            SENSORS_TYPE_BYTES: {
                KEY_SENSORS: SENSORS_BYTES,
                KEY_METHOD: self._get_bytes,
            },
            SENSORS_TYPE_LOAD_AVG: {
                KEY_SENSORS: sensors_loadavg,
                KEY_METHOD: self._get_load_avg,
            },
            SENSORS_TYPE_RATES: {
                KEY_SENSORS: SENSORS_RATES,
                KEY_METHOD: self._get_rates,
            },
            SENSORS_TYPE_TEMPERATURES: {
                KEY_SENSORS: sensors_temperatures,
                KEY_METHOD: self._get_temperatures,
            },
        }

    async def _get_available_temperature_sensors(self) -> list[str]:
        """Check which temperature information is available on the router."""
        try:
            available_temps = await self._api.async_get_temperatures()
            available_sensors = [
                t for t in SENSORS_TEMPERATURES if t in available_temps
            ]
        except AsusWrtError as exc:
            _LOGGER.warning(
                (
                    "Failed checking temperature sensor availability for ASUS router"
                    " %s. Exception: %s"
                ),
                self.host,
                exc,
            )
            return []
        return available_sensors

    async def _get_loadavg_sensors_availability(self) -> list[str]:
        """Check if load avg is available on the router."""
        try:
            await self._api.async_get_loadavg()
        except AsusWrtNotAvailableInfoError:
            return []
        except AsusWrtError:
            pass
        return SENSORS_LOAD_AVG

    @handle_errors_and_zip(AsusWrtError, SENSORS_BYTES)
    async def _get_bytes(self) -> Any:
        """Fetch byte information from the router."""
        return await self._api.async_get_traffic_bytes()

    @handle_errors_and_zip(AsusWrtError, SENSORS_RATES)
    async def _get_rates(self) -> Any:
        """Fetch rates information from the router."""
        return await self._api.async_get_traffic_rates()

    @handle_errors_and_zip(AsusWrtError, SENSORS_LOAD_AVG)
    async def _get_load_avg(self) -> Any:
        """Fetch cpu load avg information from the router."""
        return await self._api.async_get_loadavg()

    @handle_errors_and_zip(AsusWrtError, None)
    async def _get_temperatures(self) -> Any:
        """Fetch temperatures information from the router."""
        return await self._api.async_get_temperatures()
