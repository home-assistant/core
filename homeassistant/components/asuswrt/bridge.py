"""aioasuswrt and pyasuswrt bridge classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Coroutine
import functools
import logging
from typing import Any, NamedTuple

from aioasuswrt.asuswrt import AsusWrt as AsusWrtLegacy
from aiohttp import ClientSession
from asusrouter import AsusRouter, AsusRouterError
from asusrouter.config import ARConfigKey
from asusrouter.modules.client import AsusClient
from asusrouter.modules.connection import ConnectionState
from asusrouter.modules.data import AsusData
from asusrouter.modules.homeassistant import convert_to_ha_data, convert_to_ha_sensors
from asusrouter.tools.connection import get_cookie_jar

from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
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
    SENSORS_MEMORY,
    SENSORS_RATES,
    SENSORS_TEMPERATURES_LEGACY,
    SENSORS_UPTIME,
)
from .helpers import clean_dict, translate_to_legacy

SENSORS_TYPE_BYTES = "sensors_bytes"
SENSORS_TYPE_COUNT = "sensors_count"
SENSORS_TYPE_CPU = "sensors_cpu"
SENSORS_TYPE_LOAD_AVG = "sensors_load_avg"
SENSORS_TYPE_MEMORY = "sensors_memory"
SENSORS_TYPE_RATES = "sensors_rates"
SENSORS_TYPE_TEMPERATURES = "sensors_temperatures"
SENSORS_TYPE_UPTIME = "sensors_uptime"


class WrtDevice(NamedTuple):
    """WrtDevice structure."""

    ip: str | None
    name: str | None
    conneted_to: str | None


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
        async def _wrapper(self: _AsusWrtBridgeT) -> dict[str, str]:
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
            session = async_create_clientsession(
                hass,
                cookie_jar=get_cookie_jar(),
            )
            return AsusWrtHttpBridge(conf, session)
        return AsusWrtLegacyBridge(conf, options)

    def __init__(self, host: str) -> None:
        """Initialize Bridge."""
        self._configuration_url = f"http://{host}"
        self._host = host
        self._firmware: str | None = None
        self._label_mac: str | None = None
        self._model: str | None = None
        self._model_id: str | None = None
        self._serial_number: str | None = None

    @property
    def configuration_url(self) -> str:
        """Return configuration URL."""
        return self._configuration_url

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
    def model_id(self) -> str | None:
        """Return model_id information."""
        return self._model_id

    @property
    def serial_number(self) -> str | None:
        """Return serial number information."""
        return self._serial_number

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
        return self._api.is_connected

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
        await self._api.async_disconnect()

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
        # Get API configuration
        config = self._get_api_config()
        self._api = self._get_api(conf, session, config)

    @staticmethod
    def _get_api(
        conf: dict[str, Any], session: ClientSession, config: dict[ARConfigKey, Any]
    ) -> AsusRouter:
        """Get the AsusRouter API."""
        return AsusRouter(
            hostname=conf[CONF_HOST],
            username=conf[CONF_USERNAME],
            password=conf.get(CONF_PASSWORD, ""),
            use_ssl=conf[CONF_PROTOCOL] == PROTOCOL_HTTPS,
            port=conf.get(CONF_PORT),
            session=session,
            config=config,
        )

    def _get_api_config(self) -> dict[ARConfigKey, Any]:
        """Get configuration for the API."""
        return {
            # Enable automatic temperature data correction in the library
            ARConfigKey.OPTIMISTIC_TEMPERATURE: True,
            # Disable `warning`-level log message when temperature
            # is corrected by setting it to already notified.
            ARConfigKey.NOTIFIED_OPTIMISTIC_TEMPERATURE: True,
        }

    @property
    def is_connected(self) -> bool:
        """Get connected status."""
        return self._api.connected

    async def async_connect(self) -> None:
        """Connect to the device."""
        await self._api.async_connect()

        # Collect the identity
        _identity = await self._api.async_get_identity()

        # get main router properties
        if mac := _identity.mac:
            self._label_mac = format_mac(mac)
        self._configuration_url = self._api.webpanel
        self._firmware = str(_identity.firmware)
        self._model = _identity.model
        self._model_id = _identity.product_id
        self._serial_number = _identity.serial

    async def async_disconnect(self) -> None:
        """Disconnect to the device."""
        await self._api.async_disconnect()

    async def _get_data(
        self,
        datatype: AsusData,
        force: bool = False,
    ) -> dict[str, Any]:
        """Get data from the device.

        This is a generic method which automatically converts to
        the Home Assistant-compatible format.
        """
        try:
            raw = await self._api.async_get_data(datatype, force=force)
            return translate_to_legacy(clean_dict(convert_to_ha_data(raw)))
        except AsusRouterError as ex:
            raise UpdateFailed(ex) from ex

    async def _get_sensors(self, datatype: AsusData) -> list[str]:
        """Get the available sensors.

        This is a generic method which automatically converts to
        the Home Assistant-compatible format.
        """
        sensors = []
        try:
            data = await self._api.async_get_data(datatype)
            # Get the list of sensors from the raw data
            # and translate in to the legacy format
            sensors = translate_to_legacy(convert_to_ha_sensors(data, datatype))
            _LOGGER.debug("Available `%s` sensors: %s", datatype.value, sensors)
        except AsusRouterError as ex:
            _LOGGER.warning(
                "Cannot get available `%s` sensors with exception: %s",
                datatype.value,
                ex,
            )
        return sensors

    async def async_get_connected_devices(self) -> dict[str, WrtDevice]:
        """Get list of connected devices."""
        api_devices: dict[str, AsusClient] = await self._api.async_get_data(
            AsusData.CLIENTS, force=True
        )
        return {
            format_mac(mac): WrtDevice(
                dev.connection.ip_address, dev.description.name, dev.connection.node
            )
            for mac, dev in api_devices.items()
            if dev.connection is not None
            and dev.description is not None
            and dev.connection.ip_address is not None
            and dev.state is ConnectionState.CONNECTED
        }

    async def async_get_available_sensors(self) -> dict[str, dict[str, Any]]:
        """Return a dictionary of available sensors for this bridge."""
        return {
            SENSORS_TYPE_BYTES: {
                KEY_SENSORS: SENSORS_BYTES,
                KEY_METHOD: self._get_bytes,
            },
            SENSORS_TYPE_CPU: {
                KEY_SENSORS: await self._get_sensors(AsusData.CPU),
                KEY_METHOD: self._get_cpu_usage,
            },
            SENSORS_TYPE_LOAD_AVG: {
                KEY_SENSORS: await self._get_sensors(AsusData.SYSINFO),
                KEY_METHOD: self._get_load_avg,
            },
            SENSORS_TYPE_MEMORY: {
                KEY_SENSORS: SENSORS_MEMORY,
                KEY_METHOD: self._get_memory_usage,
            },
            SENSORS_TYPE_RATES: {
                KEY_SENSORS: SENSORS_RATES,
                KEY_METHOD: self._get_rates,
            },
            SENSORS_TYPE_UPTIME: {
                KEY_SENSORS: SENSORS_UPTIME,
                KEY_METHOD: self._get_uptime,
            },
            SENSORS_TYPE_TEMPERATURES: {
                KEY_SENSORS: await self._get_sensors(AsusData.TEMPERATURE),
                KEY_METHOD: self._get_temperatures,
            },
        }

    async def _get_bytes(self) -> Any:
        """Fetch byte information from the router."""
        return await self._get_data(AsusData.NETWORK)

    async def _get_rates(self) -> Any:
        """Fetch rates information from the router."""
        data = await self._get_data(AsusData.NETWORK)
        # Convert from bits/s to Bytes/s for compatibility with legacy sensors
        return {
            key: (
                value / 8
                if key in SENSORS_RATES and isinstance(value, (int, float))
                else value
            )
            for key, value in data.items()
        }

    async def _get_load_avg(self) -> Any:
        """Fetch cpu load avg information from the router."""
        return await self._get_data(AsusData.SYSINFO)

    async def _get_temperatures(self) -> Any:
        """Fetch temperatures information from the router."""
        return await self._get_data(AsusData.TEMPERATURE)

    async def _get_cpu_usage(self) -> Any:
        """Fetch cpu information from the router."""
        return await self._get_data(AsusData.CPU)

    async def _get_memory_usage(self) -> Any:
        """Fetch memory information from the router."""
        return await self._get_data(AsusData.RAM)

    async def _get_uptime(self) -> dict[str, Any]:
        """Fetch uptime from the router."""
        return await self._get_data(AsusData.BOOTTIME)
