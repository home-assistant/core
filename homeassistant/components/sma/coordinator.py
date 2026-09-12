"""Coordinator for the SMA integration."""

from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import override

from pysma import (
    ModbusControl,
    SmaAuthenticationException,
    SmaConnectionException,
    SMAModbus,
    SmaReadException,
    SmaSunSpecException,
    SmaTimeoutException,
    SMAWebConnect,
)
from pysma.helpers import DeviceInfo
from pysma.sensor import Sensors

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class SMACoordinatorData:
    """Data class for SMA sensors."""

    sma_device_info: DeviceInfo
    sensors: Sensors
    modbus_controls: dict[ModbusControl, float | None] = field(default_factory=dict)


class SMADataUpdateCoordinator(DataUpdateCoordinator[SMACoordinatorData]):
    """Data Update Coordinator for SMA."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        sma: SMAWebConnect,
        sma_modbus: SMAModbus,
    ) -> None:
        """Initialize the SMA Data Update Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                )
            ),
        )
        self.sma = sma
        self.sma_modbus = sma_modbus
        self._sma_device_info = DeviceInfo()
        self._sensors = Sensors()
        self._sma_modbus_connected = False
        self._sma_modbus_controls: dict[ModbusControl, tuple[float, float]] = {}

    @property
    def supported_modbus_controls(self) -> dict[ModbusControl, tuple[float, float]]:
        """Return the Modbus controls supported by this device, keyed by their (min, max) range."""
        return self._sma_modbus_controls

    @override
    async def _async_setup(self) -> None:
        """Setup the SMA Data Update Coordinator."""
        try:
            self._sma_device_info = await self.sma.device_info()
            self._sensors = await self.sma.get_sensors()
        except (
            SmaReadException,
            SmaConnectionException,
        ) as err:
            await self.async_close_sma_session()
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except SmaAuthenticationException as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err

        # Modbus is an optional, secondary connection that can take up to
        # ~10s to time out when unsupported
        # So, making it a background, just to be sure.:)
        self.config_entry.async_create_background_task(
            self.hass,
            self._async_discover_modbus(),
            "sma_modbus_discovery",
        )

    async def _async_discover_modbus(self) -> None:
        """Connect to and discover the SMA Modbus controls, if available."""
        try:
            await self.sma_modbus.connect()
            await self.sma_modbus.discover()

            self._sma_modbus_controls = {
                control: schema
                for control in ModbusControl
                if (schema := self.sma_modbus.get_control_schema(control)) is not None
            }

            self._sma_modbus_connected = True
        except (SmaConnectionException, SmaTimeoutException) as err:
            _LOGGER.debug("SMA Modbus connection failed: %s", err)
            return
        except SmaSunSpecException as err:
            _LOGGER.debug("SMA Modbus SunSpec discovery failed: %s", err)
            return
        else:
            await self.async_request_refresh()

    @override
    async def _async_update_data(self) -> SMACoordinatorData:
        """Update the used SMA sensors."""
        try:
            await self.sma.read(self._sensors)
        except (
            SmaReadException,
            SmaConnectionException,
        ) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except SmaAuthenticationException as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err

        modbus_controls: dict[ModbusControl, float | None] = {}
        if self._sma_modbus_connected:
            for control in self._sma_modbus_controls:
                try:
                    modbus_controls[control] = await self.sma_modbus.get_control(
                        control
                    )
                except (
                    SmaConnectionException,
                    SmaReadException,
                    SmaTimeoutException,
                ) as err:
                    _LOGGER.warning(
                        "Could not read SMA Modbus control %s: %s", control, err
                    )
                    modbus_controls[control] = None

        return SMACoordinatorData(
            sma_device_info=self._sma_device_info,
            sensors=self._sensors,
            modbus_controls=modbus_controls,
        )

    async def async_close_sma_session(self) -> None:
        """Close the SMA session."""
        await self.sma.close_session()
        _LOGGER.debug("SMA session closed")
        if self._sma_modbus_connected:
            await self.sma_modbus.close()
            _LOGGER.debug("SMA Modbus connection closed")
