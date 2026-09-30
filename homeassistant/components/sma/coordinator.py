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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, ISSUE_MODBUS_UNREACHABLE

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
        sma_modbus: SMAModbus | None,
    ) -> None:
        """Initialize the SMA Data Update Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.sma = sma
        self.sma_modbus = sma_modbus
        self._sma_device_info = DeviceInfo()
        self._sensors = Sensors()
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

        if self.sma_modbus is None:
            return

        try:
            await self.sma_modbus.connect()
            await self.sma_modbus.discover()
        except (
            SmaConnectionException,
            SmaTimeoutException,
            SmaSunSpecException,
        ) as err:
            _LOGGER.warning("Could not connect to SMA Modbus: %s", err)
            await self.sma_modbus.close()
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"{ISSUE_MODBUS_UNREACHABLE}_{self.config_entry.entry_id}",
                data={"entry_id": self.config_entry.entry_id},
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_MODBUS_UNREACHABLE,
                translation_placeholders={"name": self.config_entry.title},
            )
            return

        self._sma_modbus_controls = {
            control: schema
            for control in ModbusControl
            if (schema := self.sma_modbus.get_control_schema(control)) is not None
        }

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
        if self.sma_modbus is not None:
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
        """Close the SMA session and the Modbus connection."""
        if self.sma_modbus is not None:
            await self.sma_modbus.close()
        try:
            await self.sma.close_session()
        except SmaConnectionException as err:
            _LOGGER.debug("Could not close the SMA session: %s", err)
            return
        _LOGGER.debug("SMA session closed")
