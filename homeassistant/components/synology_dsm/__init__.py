"""The Synology DSM component."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import async_timeout
from synology_dsm.api.surveillance_station import SynoSurveillanceStation
from synology_dsm.api.surveillance_station.camera import SynoCamera
from synology_dsm.exceptions import (
    SynologyDSMAPIErrorException,
    SynologyDSMLogin2SARequiredException,
    SynologyDSMLoginDisabledAccountException,
    SynologyDSMLoginFailedException,
    SynologyDSMLoginInvalidException,
    SynologyDSMLoginPermissionDeniedException,
    SynologyDSMRequestException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_SCAN_INTERVAL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    async_get_registry as get_dev_reg,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .common import SynoApi
from .const import (
    COORDINATOR_CAMERAS,
    COORDINATOR_CENTRAL,
    COORDINATOR_SWITCHES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    EXCEPTION_DETAILS,
    EXCEPTION_UNKNOWN,
    PLATFORMS,
    SYNO_API,
    SYSTEM_LOADED,
    UNDO_UPDATE_LISTENER,
    SynologyDSMEntityDescription,
)
from .service import async_setup_services

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


ATTRIBUTION = "Data provided by Synology"


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Synology DSM sensors."""

    # Migrate device indentifiers
    dev_reg = await get_dev_reg(hass)
    devices: list[DeviceEntry] = device_registry.async_entries_for_config_entry(
        dev_reg, entry.entry_id
    )
    for device in devices:
        old_identifier = list(next(iter(device.identifiers)))
        if len(old_identifier) > 2:
            new_identifier = {
                (old_identifier.pop(0), "_".join([str(x) for x in old_identifier]))
            }
            _LOGGER.debug(
                "migrate identifier '%s' to '%s'", device.identifiers, new_identifier
            )
            dev_reg.async_update_device(device.id, new_identifiers=new_identifier)

    # Migrate existing entry configuration
    if entry.data.get(CONF_VERIFY_SSL) is None:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL}
        )

    # Continue setup
    api = SynoApi(hass, entry)
    try:
        await api.async_setup()
    except (
        SynologyDSMLogin2SARequiredException,
        SynologyDSMLoginDisabledAccountException,
        SynologyDSMLoginInvalidException,
        SynologyDSMLoginPermissionDeniedException,
    ) as err:
        if err.args[0] and isinstance(err.args[0], dict):
            details = err.args[0].get(EXCEPTION_DETAILS, EXCEPTION_UNKNOWN)
        else:
            details = EXCEPTION_UNKNOWN
        raise ConfigEntryAuthFailed(f"reason: {details}") from err
    except (SynologyDSMLoginFailedException, SynologyDSMRequestException) as err:
        if err.args[0] and isinstance(err.args[0], dict):
            details = err.args[0].get(EXCEPTION_DETAILS, EXCEPTION_UNKNOWN)
        else:
            details = EXCEPTION_UNKNOWN
        raise ConfigEntryNotReady(details) from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.unique_id] = {
        UNDO_UPDATE_LISTENER: entry.add_update_listener(_async_update_listener),
        SYNO_API: api,
        SYSTEM_LOADED: True,
    }

    # Services
    await async_setup_services(hass)

    # For SSDP compat
    if not entry.data.get(CONF_MAC):
        network = await hass.async_add_executor_job(getattr, api.dsm, "network")
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_MAC: network.macs}
        )

    async def async_coordinator_update_data_cameras() -> dict[
        str, dict[str, SynoCamera]
    ] | None:
        """Fetch all camera data from api."""
        if not hass.data[DOMAIN][entry.unique_id][SYSTEM_LOADED]:
            raise UpdateFailed("System not fully loaded")

        if SynoSurveillanceStation.CAMERA_API_KEY not in api.dsm.apis:
            return None

        surveillance_station = api.surveillance_station

        try:
            async with async_timeout.timeout(30):
                await hass.async_add_executor_job(surveillance_station.update)
        except SynologyDSMAPIErrorException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        return {
            "cameras": {
                camera.id: camera for camera in surveillance_station.get_all_cameras()
            }
        }

    async def async_coordinator_update_data_central() -> None:
        """Fetch all device and sensor data from api."""
        try:
            await api.async_update()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        return None

    async def async_coordinator_update_data_switches() -> dict[
        str, dict[str, Any]
    ] | None:
        """Fetch all switch data from api."""
        if not hass.data[DOMAIN][entry.unique_id][SYSTEM_LOADED]:
            raise UpdateFailed("System not fully loaded")
        if SynoSurveillanceStation.HOME_MODE_API_KEY not in api.dsm.apis:
            return None

        surveillance_station = api.surveillance_station

        return {
            "switches": {
                "home_mode": await hass.async_add_executor_job(
                    surveillance_station.get_home_mode_status
                )
            }
        }

    hass.data[DOMAIN][entry.unique_id][COORDINATOR_CAMERAS] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{entry.unique_id}_cameras",
        update_method=async_coordinator_update_data_cameras,
        update_interval=timedelta(seconds=30),
    )

    hass.data[DOMAIN][entry.unique_id][COORDINATOR_CENTRAL] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{entry.unique_id}_central",
        update_method=async_coordinator_update_data_central,
        update_interval=timedelta(
            minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        ),
    )

    hass.data[DOMAIN][entry.unique_id][COORDINATOR_SWITCHES] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{entry.unique_id}_switches",
        update_method=async_coordinator_update_data_switches,
        update_interval=timedelta(seconds=30),
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Synology DSM sensors."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data[DOMAIN][entry.unique_id]
        entry_data[UNDO_UPDATE_LISTENER]()
        await entry_data[SYNO_API].async_unload()
        hass.data[DOMAIN].pop(entry.unique_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class SynologyDSMBaseEntity(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, dict[str, Any]]]]
):
    """Representation of a Synology NAS entry."""

    entity_description: SynologyDSMEntityDescription
    unique_id: str
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        api: SynoApi,
        coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]],
        description: SynologyDSMEntityDescription,
    ) -> None:
        """Initialize the Synology DSM entity."""
        super().__init__(coordinator)
        self.entity_description = description

        self._api = api
        self._attr_name = f"{api.network.hostname} {description.name}"
        self._attr_unique_id: str = (
            f"{api.information.serial}_{description.api_key}:{description.key}"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._api.information.serial)},
            name="Synology NAS",
            manufacturer="Synology",
            model=self._api.information.model,
            sw_version=self._api.information.version_string,
            configuration_url=self._api.config_url,
        )

    async def async_added_to_hass(self) -> None:
        """Register entity for updates from API."""
        self.async_on_remove(
            self._api.subscribe(self.entity_description.api_key, self.unique_id)
        )
        await super().async_added_to_hass()


class SynologyDSMDeviceEntity(SynologyDSMBaseEntity):
    """Representation of a Synology NAS disk or volume entry."""

    def __init__(
        self,
        api: SynoApi,
        coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]],
        description: SynologyDSMEntityDescription,
        device_id: str | None = None,
    ) -> None:
        """Initialize the Synology DSM disk or volume entity."""
        super().__init__(api, coordinator, description)
        self._device_id = device_id
        self._device_name: str | None = None
        self._device_manufacturer: str | None = None
        self._device_model: str | None = None
        self._device_firmware: str | None = None
        self._device_type = None

        if "volume" in description.key:
            volume = self._api.storage.get_volume(self._device_id)
            # Volume does not have a name
            self._device_name = volume["id"].replace("_", " ").capitalize()
            self._device_manufacturer = "Synology"
            self._device_model = self._api.information.model
            self._device_firmware = self._api.information.version_string
            self._device_type = (
                volume["device_type"]
                .replace("_", " ")
                .replace("raid", "RAID")
                .replace("shr", "SHR")
            )
        elif "disk" in description.key:
            disk = self._api.storage.get_disk(self._device_id)
            self._device_name = disk["name"]
            self._device_manufacturer = disk["vendor"]
            self._device_model = disk["model"].strip()
            self._device_firmware = disk["firm"]
            self._device_type = disk["diskType"]
        self._name = (
            f"{self._api.network.hostname} {self._device_name} {description.name}"
        )
        self._attr_unique_id += f"_{self._device_id}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._api.storage  # type: ignore [no-any-return]

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._api.information.serial}_{self._device_id}")},
            name=f"Synology NAS ({self._device_name} - {self._device_type})",
            manufacturer=self._device_manufacturer,
            model=self._device_model,
            sw_version=self._device_firmware,
            via_device=(DOMAIN, self._api.information.serial),
            configuration_url=self._api.config_url,
        )
