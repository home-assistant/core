"""The Fronius integration."""

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Final
from urllib.parse import urlsplit

from fronius_modbus import (
    GEN24_UNIT_ID,
    FroniusModbusInverter,
    SunSpecError,
    datamanager_unit_id,
)
from modbus_connection import ModbusError, ModbusTcpParams
from pyfronius import Fronius, FroniusError

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_MODEL, ATTR_SW_VERSION, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_MODBUS_PORT,
    DEFAULT_MODBUS_PORT,
    DOMAIN,
    SOLAR_NET_DISCOVERY_NEW,
    SOLAR_NET_ID_SYSTEM,
    SOLAR_NET_RESCAN_TIMER,
    FroniusDeviceInfo,
    SolarNetId,
)
from .coordinator import (
    FroniusCoordinatorBase,
    FroniusInverterUpdateCoordinator,
    FroniusLoggerUpdateCoordinator,
    FroniusMeterUpdateCoordinator,
    FroniusModbusInverterUpdateCoordinator,
    FroniusModbusSettingsUpdateCoordinator,
    FroniusOhmpilotUpdateCoordinator,
    FroniusPowerFlowUpdateCoordinator,
    FroniusStorageUpdateCoordinator,
)

_LOGGER: Final = logging.getLogger(__name__)
PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

type FroniusConfigEntry = ConfigEntry[FroniusSolarNet]


async def async_setup_entry(hass: HomeAssistant, entry: FroniusConfigEntry) -> bool:
    """Set up fronius from a config entry."""
    host = entry.data[CONF_HOST]
    fronius = Fronius(
        async_get_clientsession(
            hass,
            # Fronius Gen24 firmware 1.35.4-1 redirects to HTTPS with self-signed
            # certificate. See https://github.com/home-assistant/core/issues/138881
            verify_ssl=False,
        ),
        host,
    )
    solar_net = FroniusSolarNet(hass, entry, fronius)
    await solar_net.init_devices()

    entry.runtime_data = solar_net
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: FroniusConfigEntry) -> bool:
    """Migrate old config entries."""
    if entry.minor_version < 2:
        # add the Modbus port setting
        data = {CONF_MODBUS_PORT: DEFAULT_MODBUS_PORT, **entry.data}
        hass.config_entries.async_update_entry(entry, data=data, minor_version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FroniusConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: FroniusConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    return True


class FroniusSolarNet:
    """The FroniusSolarNet class routes received values to sensor entities."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, fronius: Fronius
    ) -> None:
        """Initialize FroniusSolarNet class."""
        self.hass = hass
        self.config_entry = entry
        self.coordinator_lock = asyncio.Lock()
        self.fronius = fronius
        self.host: str = entry.data[CONF_HOST]
        # entry.unique_id is either logger uid or first inverter
        # uid if no logger available prepended by "solar_net_"
        # to have individual device for whole system (power_flow)
        self.solar_net_device_id = f"solar_net_{entry.unique_id}"
        self.system_device_info: DeviceInfo | None = None

        self.inverter_coordinators: list[FroniusInverterUpdateCoordinator] = []
        self.logger_coordinator: FroniusLoggerUpdateCoordinator | None = None
        self.meter_coordinator: FroniusMeterUpdateCoordinator | None = None
        self.ohmpilot_coordinator: FroniusOhmpilotUpdateCoordinator | None = None
        self.power_flow_coordinator: FroniusPowerFlowUpdateCoordinator | None = None
        self.storage_coordinator: FroniusStorageUpdateCoordinator | None = None

        self.modbus_inverter_coordinators: list[
            FroniusModbusInverterUpdateCoordinator
        ] = []
        self.modbus_settings_coordinators: list[
            FroniusModbusSettingsUpdateCoordinator
        ] = []
        # one hold on the shared connection per inverter, kept across re-scans
        self.modbus_inverters: dict[SolarNetId, FroniusModbusInverter] = {}

    async def init_devices(self) -> None:
        """Initialize DataUpdateCoordinators for SolarNet devices."""
        if self.config_entry.data["is_logger"]:
            self.logger_coordinator = FroniusLoggerUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_logger_{self.host}",
                config_entry=self.config_entry,
            )
            await self.logger_coordinator.async_config_entry_first_refresh()

        # _create_solar_net_device uses data from self.logger_coordinator when available
        self.system_device_info = await self._create_solar_net_device()

        await self._init_devices_inverter()

        self.meter_coordinator = await self._init_optional_coordinator(
            FroniusMeterUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_meters_{self.host}",
                config_entry=self.config_entry,
            )
        )

        self.ohmpilot_coordinator = await self._init_optional_coordinator(
            FroniusOhmpilotUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_ohmpilot_{self.host}",
                config_entry=self.config_entry,
            )
        )

        self.power_flow_coordinator = await self._init_optional_coordinator(
            FroniusPowerFlowUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_power_flow_{self.host}",
                config_entry=self.config_entry,
            )
        )

        self.storage_coordinator = await self._init_optional_coordinator(
            FroniusStorageUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_storages_{self.host}",
                config_entry=self.config_entry,
            )
        )

        # Setup periodic re-scan
        self.config_entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                self._init_devices_inverter,
                timedelta(minutes=SOLAR_NET_RESCAN_TIMER),
            )
        )

    async def _create_solar_net_device(self) -> DeviceInfo:
        """Create a device for the Fronius SolarNet system."""
        solar_net_device: DeviceInfo = DeviceInfo(
            configuration_url=self.fronius.url,
            identifiers={(DOMAIN, self.solar_net_device_id)},
            manufacturer="Fronius",
            name="SolarNet",
        )
        if self.logger_coordinator:
            _logger_info = self.logger_coordinator.data[SOLAR_NET_ID_SYSTEM]
            # API v0 doesn't provide product_type
            solar_net_device[ATTR_MODEL] = _logger_info.get("product_type", {}).get(
                "value", "Datalogger Web"
            )
            solar_net_device[ATTR_SW_VERSION] = _logger_info["software_version"][
                "value"
            ]

        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            **solar_net_device,
        )
        return solar_net_device

    async def _init_devices_inverter(self, _now: datetime | None = None) -> None:
        """Get available inverters and set up coordinators for new found devices."""
        _inverter_infos = await self._get_inverter_infos()

        _LOGGER.debug("Processing inverters for: %s", _inverter_infos)
        for _inverter_info in _inverter_infos:
            _inverter_name = (
                f"{DOMAIN}_inverter_{_inverter_info.solar_net_id}_{self.host}"
            )

            # Add found inverter only not already existing
            if _inverter_info.solar_net_id in [
                inv.inverter_info.solar_net_id for inv in self.inverter_coordinators
            ]:
                continue

            _coordinator = FroniusInverterUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=_inverter_name,
                inverter_info=_inverter_info,
                config_entry=self.config_entry,
            )
            if self.config_entry.state is ConfigEntryState.LOADED:
                await _coordinator.async_refresh()
            else:
                await _coordinator.async_config_entry_first_refresh()
            self.inverter_coordinators.append(_coordinator)

            # Only for re-scans. Initial setup adds entities
            # through sensor.async_setup_entry
            if self.config_entry.state is ConfigEntryState.LOADED:
                async_dispatcher_send(self.hass, SOLAR_NET_DISCOVERY_NEW, _coordinator)

            _LOGGER.debug(
                "New inverter added (UID: %s)",
                _inverter_info.unique_id,
            )

        # an inverter that was asleep answers nothing, so retry the ones
        # still without Modbus data on every re-scan
        for inverter_coordinator in self.inverter_coordinators:
            await self._init_modbus_inverter(inverter_coordinator.inverter_info)

    async def _get_inverter_infos(self) -> list[FroniusDeviceInfo]:
        """Get information about the inverters in the SolarNet system."""
        inverter_infos: list[FroniusDeviceInfo] = []

        try:
            _inverter_info = await self.fronius.inverter_info()
        except FroniusError as err:
            if self.config_entry.state is ConfigEntryState.LOADED:
                # During a re-scan we will attempt again as per schedule.
                _LOGGER.debug("Re-scan failed for %s", self.host)
                return inverter_infos

            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="entry_cannot_connect",
                translation_placeholders={
                    "host": self.host,
                    "fronius_error": str(err),
                },
            ) from err

        for inverter in _inverter_info["inverters"]:
            solar_net_id = inverter["device_id"]["value"]
            unique_id = inverter["unique_id"]["value"]
            device_info = DeviceInfo(
                identifiers={(DOMAIN, unique_id)},
                manufacturer=inverter["device_type"].get("manufacturer", "Fronius"),
                model=inverter["device_type"].get(
                    "model", inverter["device_type"]["value"]
                ),
                name=inverter.get("custom_name", {}).get("value"),
                via_device_id=dr.async_get_device_id_by_identifier(
                    self.hass,
                    (DOMAIN, self.solar_net_device_id),
                    config_entry_id=self.config_entry.entry_id,
                ),
            )
            inverter_infos.append(
                FroniusDeviceInfo(
                    device_info=device_info,
                    solar_net_id=solar_net_id,
                    unique_id=unique_id,
                )
            )
            _LOGGER.debug(
                "Inverter found at %s (Device ID: %s, UID: %s)",
                self.host,
                solar_net_id,
                unique_id,
            )
        return inverter_infos

    def _modbus_params(self) -> ModbusTcpParams | None:
        """Return the Modbus link settings, or None for an unusable host."""
        # the configured host may be a bare host name or a full URL
        url = self.host if "://" in self.host else f"//{self.host}"
        if (modbus_host := urlsplit(url).hostname) is None:
            return None
        return ModbusTcpParams(
            host=modbus_host, port=self.config_entry.data[CONF_MODBUS_PORT]
        )

    async def _init_modbus_inverter(self, inverter_info: FroniusDeviceInfo) -> None:
        """Set up a Modbus coordinator for an inverter exposing SunSpec MPPT data."""
        if inverter_info.solar_net_id in [
            coordinator.inverter_info.solar_net_id
            for coordinator in self.modbus_inverter_coordinators
        ]:
            return
        if (unit_id := self._modbus_unit_id(inverter_info.solar_net_id)) is None:
            return
        if (
            modbus_inverter := self.modbus_inverters.get(inverter_info.solar_net_id)
        ) is None:
            if (params := self._modbus_params()) is None:
                return
            try:
                unit = async_get_unit(self.hass, self.config_entry, params, unit_id)
            except HomeAssistantError as err:
                # another integration holds the device on different link settings
                _LOGGER.debug("No Modbus unit for inverter %s: %s", unit_id, err)
                return
            modbus_inverter = FroniusModbusInverter(unit)
            self.modbus_inverters[inverter_info.solar_net_id] = modbus_inverter

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
        if modbus_inverter.mppt is not None:
            readings = FroniusModbusInverterUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_modbus_inverter_{inverter_info.solar_net_id}_{self.host}",
                inverter_info=inverter_info,
                modbus_inverter=modbus_inverter,
                config_entry=self.config_entry,
            )
            if await self._start_modbus_coordinator(readings):
                self.modbus_inverter_coordinators.append(readings)
        else:
            _LOGGER.debug(
                "No MPPT model exposed by inverter %s at Modbus unit %s",
                inverter_info.solar_net_id,
                unit_id,
            )

        if await self._modbus_control_allowed(modbus_inverter, unit_id):
            settings = FroniusModbusSettingsUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_modbus_settings_{inverter_info.solar_net_id}_{self.host}",
                inverter_info=inverter_info,
                modbus_inverter=modbus_inverter,
                config_entry=self.config_entry,
            )
            if await self._start_modbus_coordinator(settings):
                self.modbus_settings_coordinators.append(settings)

        _LOGGER.debug(
            "Modbus enabled for inverter %s (UID: %s, unit ID: %s)",
            inverter_info.solar_net_id,
            inverter_info.unique_id,
            unit_id,
        )

    async def _start_modbus_coordinator(
        self, coordinator: FroniusCoordinatorBase
    ) -> bool:
        """Do the first refresh of a Modbus coordinator, reporting success.

        Not `async_config_entry_first_refresh`: Modbus data is optional, so a
        device that doesn't answer must leave the rest of the entry alone
        instead of raising `ConfigEntryNotReady`.
        """
        await coordinator.async_refresh()
        if not coordinator.last_update_success:
            return False
        # Only for re-scans. Initial setup adds entities through the
        # platforms' async_setup_entry.
        if self.config_entry.state is ConfigEntryState.LOADED:
            async_dispatcher_send(self.hass, SOLAR_NET_DISCOVERY_NEW, coordinator)
        return True

    async def _modbus_control_allowed(
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

    def _modbus_unit_id(self, solar_net_id: str) -> int | None:
        """Return the Modbus unit ID for an inverter."""
        if not self.config_entry.data["is_logger"]:
            return GEN24_UNIT_ID
        return datamanager_unit_id(solar_net_id)

    @staticmethod
    async def _init_optional_coordinator[_FroniusCoordinatorT: FroniusCoordinatorBase](
        coordinator: _FroniusCoordinatorT,
    ) -> _FroniusCoordinatorT | None:
        """Initialize an update coordinator and return it if devices are found."""
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            # ConfigEntryNotReady raised form FroniusError / KeyError in
            # DataUpdateCoordinator if request not supported by the Fronius device
            return None
        # if no device for the request is installed an empty dict is returned
        if not coordinator.data:
            return None
        return coordinator
