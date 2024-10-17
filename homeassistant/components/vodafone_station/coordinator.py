"""Support for Vodafone Station."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from aiovodafone import VodafoneStationDevice, VodafoneStationSercommApi, exceptions

from homeassistant.components.device_tracker import (
    DEFAULT_CONSIDER_HOME,
    DOMAIN as DEVICE_TRACKER_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import _LOGGER, DOMAIN

CONSIDER_HOME_SECONDS = DEFAULT_CONSIDER_HOME.total_seconds()


@dataclass(slots=True)
class VodafoneStationDeviceInfo:
    """Representation of a device connected to the Vodafone Station."""

    device: VodafoneStationDevice
    update_time: datetime | None
    home: bool


@dataclass(slots=True)
class UpdateCoordinatorDataType:
    """Update coordinator data type."""

    devices: dict[str, VodafoneStationDeviceInfo]
    sensors: dict[str, Any]


class VodafoneStationRouter(DataUpdateCoordinator[UpdateCoordinatorDataType]):
    """Queries router running Vodafone Station firmware."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
        config_entry_unique_id: str | None,
    ) -> None:
        """Initialize the scanner."""

        self._host = host
        self.api = VodafoneStationSercommApi(host, username, password)

        # Last resort as no MAC or S/N can be retrieved via API
        self._id = config_entry_unique_id

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}-{host}-coordinator",
            update_interval=timedelta(seconds=30),
        )

    def _calculate_update_time_and_consider_home(
        self, device: VodafoneStationDevice, utc_point_in_time: datetime
    ) -> tuple[datetime | None, bool]:
        """Return update time and consider home.

        If the device is connected, return the current time and True.

        If the device is not connected, return the last update time and
        whether the device was considered home at that time.

        If the device is not connected and there is no last update time,
        return None and False.
        """
        if device.connected:
            return utc_point_in_time, True

        if (
            (data := self.data)
            and (stored_device := data.devices.get(device.mac))
            and (update_time := stored_device.update_time)
        ):
            return (
                update_time,
                (
                    (utc_point_in_time - update_time).total_seconds()
                    < CONSIDER_HOME_SECONDS
                ),
            )

        return None, False

    async def _async_update_data(self) -> UpdateCoordinatorDataType:
        """Update router data."""
        _LOGGER.debug("Polling Vodafone Station host: %s", self._host)
        try:
            try:
                await self.api.login()
                raw_data_devices = await self.api.get_devices_data()
                data_sensors = await self.api.get_sensor_data()
                await self.api.logout()
            except exceptions.CannotAuthenticate as err:
                raise ConfigEntryAuthFailed from err
            except (
                exceptions.CannotConnect,
                exceptions.AlreadyLogged,
                exceptions.GenericLoginError,
            ) as err:
                raise UpdateFailed(f"Error fetching data: {err!r}") from err
        except (ConfigEntryAuthFailed, UpdateFailed):
            await self.api.close()
            raise

        utc_point_in_time = dt_util.utcnow()
        data_devices = {
            dev_info.mac: VodafoneStationDeviceInfo(
                dev_info,
                *self._calculate_update_time_and_consider_home(
                    dev_info, utc_point_in_time
                ),
            )
            for dev_info in (raw_data_devices).values()
        }
        return UpdateCoordinatorDataType(data_devices, data_sensors)

    async def cleanup_device_tracker_entities(self) -> None:
        """Clean old device trackers entities."""
        entity_reg: er.EntityRegistry = er.async_get(self.hass)

        ha_entity_reg_list: list[er.RegistryEntry] = er.async_entries_for_config_entry(
            entity_reg, self.config_entry.entry_id
        )
        entities_removed: bool = False

        device_hosts_macs = set()
        device_hosts_names = set()
        for mac, device_info in self.data.devices.items():
            device_hosts_macs.add(mac)
            device_hosts_names.add(device_info.device.name)

        for entry in ha_entity_reg_list:
            if entry.original_name is None:
                continue
            entry_name = entry.name or entry.original_name
            entry_host = entry_name.split(" ")[0]
            entry_mac = entry.unique_id.split("_")[0]

            if entry.platform != DEVICE_TRACKER_DOMAIN or (
                entry_mac in device_hosts_macs and entry_host in device_hosts_names
            ):
                _LOGGER.debug(
                    "Skipping entity %s [mac=%s, host=%s]",
                    entry_name,
                    entry_mac,
                    entry_host,
                )
                continue
            _LOGGER.info("Removing entity: %s", entry_name)
            entity_reg.async_remove(entry.entity_id)
            entities_removed = True

        if entities_removed:
            self._async_remove_empty_devices(entity_reg, self.config_entry)

    @callback
    def _async_remove_empty_devices(
        self, entity_reg: er.EntityRegistry, config_entry: ConfigEntry
    ) -> None:
        """Remove devices with no entities."""

        device_reg = dr.async_get(self.hass)
        device_list = dr.async_entries_for_config_entry(
            device_reg, config_entry.entry_id
        )
        for device_entry in device_list:
            if not er.async_entries_for_device(
                entity_reg,
                device_entry.id,
                include_disabled_entities=True,
            ):
                _LOGGER.info("Removing device: %s", device_entry.name)
                device_reg.async_update_device(
                    device_entry.id, remove_config_entry_id=self.config_entry.entry_id
                )

    @property
    def signal_device_new(self) -> str:
        """Event specific per Vodafone Station entry to signal new device."""
        return f"{DOMAIN}-device-new-{self._id}"

    @property
    def serial_number(self) -> str:
        """Device serial number."""
        return self.data.sensors["sys_serial_number"]

    @property
    def device_info(self) -> DeviceInfo:
        """Set device info."""
        sensors_data = self.data.sensors
        return DeviceInfo(
            configuration_url=self.api.base_url,
            identifiers={(DOMAIN, self.serial_number)},
            name=f"Vodafone Station ({self.serial_number})",
            manufacturer="Vodafone",
            model=sensors_data.get("sys_model_name"),
            hw_version=sensors_data["sys_hardware_version"],
            sw_version=sensors_data["sys_firmware_version"],
        )
