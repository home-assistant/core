"""The Modbus side of a Fronius SolarNet system."""

import logging
from typing import TYPE_CHECKING, Final

from fronius_modbus import (
    GEN24_UNIT_ID,
    FroniusModbusInverter,
    SunSpecError,
    datamanager_unit_id,
)
from modbus_connection import ModbusError, ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_MODBUS_PORT,
    DOMAIN,
    FroniusDeviceInfo,
    SolarNetId,
    discovery_signal,
    host_from_config,
)
from .coordinator import (
    FroniusModbusCoordinatorBase,
    FroniusModbusInverterUpdateCoordinator,
    FroniusModbusSettingsUpdateCoordinator,
)

if TYPE_CHECKING:
    from .solar_net import FroniusSolarNet

_LOGGER: Final = logging.getLogger(__name__)


class FroniusModbus:
    """Set up and hold the Modbus coordinators of a SolarNet's inverters.

    Modbus data is optional: an inverter that doesn't answer leaves the
    SolarAPI side alone and is tried again on the next re-scan.
    """

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, solar_net: FroniusSolarNet
    ) -> None:
        """Initialize the Modbus side of a SolarNet."""
        self._hass = hass
        self._config_entry = entry
        self._solar_net = solar_net
        self.inverter_coordinators: list[FroniusModbusInverterUpdateCoordinator] = []
        self.settings_coordinators: list[FroniusModbusSettingsUpdateCoordinator] = []
        # one hold on the shared connection per inverter, kept across re-scans
        self._inverters: dict[SolarNetId, FroniusModbusInverter] = {}

    async def async_init_inverter(self, inverter_info: FroniusDeviceInfo) -> None:
        """Set up the Modbus coordinators an inverter has data for."""
        # each coordinator is retried on its own: a device may answer for one
        # of them and not the other, and recover on a later re-scan
        needs_readings = inverter_info.solar_net_id not in {
            coordinator.inverter_info.solar_net_id
            for coordinator in self.inverter_coordinators
        }
        needs_settings = inverter_info.solar_net_id not in {
            coordinator.inverter_info.solar_net_id
            for coordinator in self.settings_coordinators
        }
        if not needs_readings and not needs_settings:
            return
        if (unit_id := self._unit_id(inverter_info.solar_net_id)) is None:
            return
        if (modbus_inverter := self._inverters.get(inverter_info.solar_net_id)) is None:
            if (params := self._params()) is None:
                return
            try:
                unit = async_get_unit(self._hass, self._config_entry, params, unit_id)
            except HomeAssistantError as err:
                # another integration holds the device on different link settings
                _LOGGER.debug("No Modbus unit for inverter %s: %s", unit_id, err)
                return
            modbus_inverter = FroniusModbusInverter(unit)
            self._inverters[inverter_info.solar_net_id] = modbus_inverter

        try:
            await modbus_inverter.discover()
        except (ModbusError, SunSpecError) as err:
            _LOGGER.debug(
                "No SunSpec data for inverter %s at Modbus unit %s: %s",
                inverter_info.solar_net_id,
                unit_id,
                err,
            )
            return
        if needs_readings and modbus_inverter.mppt is not None:
            readings = FroniusModbusInverterUpdateCoordinator(
                hass=self._hass,
                solar_net=self._solar_net,
                logger=_LOGGER,
                name=f"{DOMAIN}_modbus_inverter_{inverter_info.solar_net_id}_{self._solar_net.host}",
                inverter_info=inverter_info,
                modbus_inverter=modbus_inverter,
                config_entry=self._config_entry,
            )
            await self._start_coordinator(readings, self.inverter_coordinators)
        elif needs_readings:
            _LOGGER.debug(
                "No MPPT model exposed by inverter %s at Modbus unit %s",
                inverter_info.solar_net_id,
                unit_id,
            )

        if needs_settings and await self._control_allowed(modbus_inverter, unit_id):
            settings = FroniusModbusSettingsUpdateCoordinator(
                hass=self._hass,
                solar_net=self._solar_net,
                logger=_LOGGER,
                name=f"{DOMAIN}_modbus_settings_{inverter_info.solar_net_id}_{self._solar_net.host}",
                inverter_info=inverter_info,
                modbus_inverter=modbus_inverter,
                config_entry=self._config_entry,
            )
            if await self._start_coordinator(settings, self.settings_coordinators):
                await settings.async_start_heartbeat()

        _LOGGER.debug(
            "Modbus enabled for inverter %s (UID: %s, unit ID: %s)",
            inverter_info.solar_net_id,
            inverter_info.unique_id,
            unit_id,
        )

    def _params(self) -> ModbusTcpParams | None:
        """Return the Modbus link settings, or None for an unusable host."""
        if (modbus_host := host_from_config(self._solar_net.host)) is None:
            return None
        return ModbusTcpParams(
            host=modbus_host, port=self._config_entry.data[CONF_MODBUS_PORT]
        )

    async def _start_coordinator[_ModbusCoordinatorT: FroniusModbusCoordinatorBase](
        self, coordinator: _ModbusCoordinatorT, coordinators: list[_ModbusCoordinatorT]
    ) -> bool:
        """Do the first refresh of a Modbus coordinator, reporting success.

        Not `async_config_entry_first_refresh`: Modbus data is optional, so a
        device that doesn't answer must leave the rest of the entry alone
        instead of raising `ConfigEntryNotReady`.
        """
        await coordinator.async_refresh()
        if not coordinator.last_update_success:
            return False
        coordinators.append(coordinator)
        # Only for re-scans. Initial setup adds entities through the
        # platforms' async_setup_entry.
        if self._config_entry.state is ConfigEntryState.LOADED:
            async_dispatcher_send(
                self._hass, discovery_signal(self._config_entry.entry_id), coordinator
            )
        return True

    async def _control_allowed(
        self, modbus_inverter: FroniusModbusInverter, unit_id: int
    ) -> bool:
        """Check whether the device accepts the writes the controls need.

        "Inverter control via Modbus" has to be enabled on the device web
        interface, and no register reports it - the only way to find out is
        to write. `probe_write_access` writes a register's own value back.
        """
        if (controls := modbus_inverter.controls) is None:
            return False
        try:
            allowed = await controls.probe_write_access()
        except (ModbusError, SunSpecError) as err:
            _LOGGER.debug("Modbus write probe failed for unit %s: %s", unit_id, err)
            return False
        if not allowed:
            _LOGGER.debug(
                "Inverter control via Modbus is not enabled on unit %s", unit_id
            )
        return allowed

    def _unit_id(self, solar_net_id: str) -> int | None:
        """Return the Modbus unit ID for an inverter."""
        if not self._config_entry.data["is_logger"]:
            return GEN24_UNIT_ID
        return datamanager_unit_id(solar_net_id)
