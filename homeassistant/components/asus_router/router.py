"""Asus Router router module."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import Any, TypeVar

from asusrouter import AsusDevice, AsusRouterConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .bridge import ARBridge
from .const import (
    CONF_DEFAULT_PORT,
    CONF_DEFAULT_PORTS,
    CONF_REQUIRE_RELOAD,
    COORDINATOR,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    HTTP,
    HTTPS,
    METHOD,
    NO_SSL,
    SENSORS,
    SSL,
)

_T = TypeVar("_T")
_LOGGER = logging.getLogger(__name__)


class ARSensorHandler:
    """Handler for Asus Router sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        bridge: ARBridge,
        options: dict[str, Any],
    ) -> None:
        """Initialize sensor handler."""

        self.hass = hass
        self.bridge = bridge
        self._options = options

    async def get_coordinator(
        self,
        sensor_type: str,
        update_method: Callable[[], Awaitable[_T]] | None = None,
    ) -> DataUpdateCoordinator:
        """Find coordinator for the sensor type."""

        # Update interval
        update_interval = timedelta(seconds=DEFAULT_UPDATE_INTERVAL)

        # Coordinator
        coordinator = DataUpdateCoordinator(
            self.hass,
            _LOGGER,
            name=sensor_type,
            update_method=update_method,
            update_interval=update_interval,
        )

        _LOGGER.debug(
            "Coordinator initialized for `%s`. Update interval: `%s`",
            sensor_type,
            update_interval,
        )

        # Update coordinator
        await coordinator.async_refresh()

        return coordinator


class ARDevice:
    """Representation of Asus router."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the device."""

        self.hass = hass
        self._config_entry = config_entry
        self._options = config_entry.options.copy()

        # Device configs
        self._conf_host: str = config_entry.data[CONF_HOST]
        self._conf_port: int = self._options[CONF_PORT]
        self._conf_name: str = ""

        if self._conf_port == CONF_DEFAULT_PORT:
            self._conf_port = (
                CONF_DEFAULT_PORTS[SSL]
                if self._options[CONF_SSL]
                else CONF_DEFAULT_PORTS[NO_SSL]
            )

        # Bridge & device information
        self.bridge = ARBridge(hass, dict(self._config_entry.data), self._options)
        self._identity: AsusDevice = AsusDevice()
        self._mac: str = ""

        # Device sensors
        self._sensor_handler: ARSensorHandler | None = None
        self._sensor_coordinator: dict[str, Any] = {}

        # On-close parameters
        self._on_close: list[Callable] = []

    async def setup(self) -> None:
        """Set up Asus router."""

        # Connect & check connection
        try:
            await self.bridge.async_connect()
        except (OSError, AsusRouterConnectionError) as ex:
            raise ConfigEntryNotReady from ex
        if not self.bridge.connected:
            raise ConfigEntryNotReady

        # Write the identity
        self._identity = self.bridge.identity
        self._mac = format_mac(self._identity.mac)

        # Use device model as the default device name
        self._conf_name = self._identity.model

        # Initialize sensor coordinators
        await self._init_sensor_coordinators()

    async def _init_sensor_coordinators(self) -> None:
        """Initialize sensor coordinators."""

        # If already initialized
        if self._sensor_handler:
            return

        # Initialize sensor handler
        self._sensor_handler = ARSensorHandler(self.hass, self.bridge, self._options)

        # Get the available sensors
        available_sensors = await self.bridge.async_get_available_sensors()

        # Process available sensors
        for sensor_type, sensor_definition in available_sensors.items():
            sensor_names = sensor_definition.get(SENSORS)
            if not sensor_names:
                continue

            # Find and initialize coordinator
            coordinator = await self._sensor_handler.get_coordinator(
                sensor_type, sensor_definition.get(METHOD)
            )

            # Save the coordinator
            self._sensor_coordinator[sensor_type] = {
                COORDINATOR: coordinator,
                sensor_type: sensor_names,
            }

    async def close(self) -> None:
        """Close the connection."""

        # Disconnect the bridge
        if self.bridge.active:
            await self.bridge.async_disconnect()

        # Run on-close methods
        for func in self._on_close:
            func()

        self._on_close.clear()

    @callback
    def async_on_close(
        self,
        func: CALLBACK_TYPE,
    ) -> None:
        """Functions on router close."""

        self._on_close.append(func)

    def update_options(
        self,
        new_options: dict[str, Any],
    ) -> bool:
        """Update router options."""

        require_reload = False
        for name, new_option in new_options.items():
            if name in CONF_REQUIRE_RELOAD:
                old_option = self._options.get(name)
                if not old_option or old_option != new_option:
                    require_reload = True
                    break

        self._options.update(new_options)
        return require_reload

    @property
    def device_info(self) -> DeviceInfo:
        """Device information."""

        return DeviceInfo(
            identifiers={
                (DOMAIN, self.mac),
                (DOMAIN, self._identity.serial),
            },
            name=self._conf_name,
            model=self._identity.model,
            manufacturer=self._identity.brand,
            sw_version=str(self._identity.firmware),
            configuration_url=f"{HTTPS if self._options[CONF_SSL] else HTTP}://\
                {self._conf_host}:{self._conf_port}",
        )

    @property
    def mac(self) -> str:
        """Router MAC address."""

        return self._mac

    @property
    def sensor_coordinator(self) -> dict[str, Any]:
        """Return sensor coordinator."""

        return self._sensor_coordinator
