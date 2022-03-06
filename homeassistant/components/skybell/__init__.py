"""Support for the Skybell HD Doorbell."""
from __future__ import annotations

from aioskybell import Skybell
from aioskybell.exceptions import SkybellAuthenticationException, SkybellException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTRIBUTION, DEFAULT_CACHEDB, DEFAULT_NAME, DOMAIN
from .coordinator import SkybellDataUpdateCoordinator

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        # Deprecated in Home Assistant 2022.4
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SkyBell component."""
    hass.data.setdefault(DOMAIN, {})

    entry_config = {}
    if DOMAIN not in config:
        return True
    for parameter in config[DOMAIN]:
        if parameter == CONF_USERNAME:
            entry_config[CONF_EMAIL] = config[DOMAIN][parameter]
        else:
            entry_config[parameter] = config[DOMAIN][parameter]
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=entry_config,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Skybell from a config entry."""
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    api = Skybell(
        username=email,
        password=password,
        get_devices=True,
        cache_path=hass.config.path(DEFAULT_CACHEDB),
        session=async_get_clientsession(hass),
    )
    try:
        devices = await api.async_initialize()
    except SkybellAuthenticationException:
        return False
    except SkybellException as ex:
        raise ConfigEntryNotReady(f"Unable to connect to Skybell service: {ex}") from ex

    device_coordinators: dict[str, DataUpdateCoordinator] = {}
    for device in devices:
        coordinator = SkybellDataUpdateCoordinator(
            hass,
            device,
        )
        await coordinator.async_config_entry_first_refresh()
        device_coordinators[device.device_id] = coordinator
    hass.data[DOMAIN][entry.entry_id] = device_coordinators
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class SkybellEntity(CoordinatorEntity):
    """An HA implementation for Skybell devices."""

    coordinator: SkybellDataUpdateCoordinator

    def __init__(
        self,
        coordinator: SkybellDataUpdateCoordinator,
    ) -> None:
        """Initialize a SkyBell entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, coordinator.device.mac)},
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            model=coordinator.device.type,
            name=coordinator.device.name,
            sw_version=coordinator.device.firmware_ver,
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device_id": self.coordinator.device.device_id,
            "status": self.coordinator.device.status,
            "location": self.coordinator.device.location,
            "wifi_ssid": self.coordinator.device.wifi_ssid,
            "wifi_status": self.coordinator.device.wifi_status,
            "last_check_in": self.coordinator.device.last_check_in,
            "motion_threshold": self.coordinator.device.motion_threshold,
            "video_profile": self.coordinator.device.video_profile,
        }

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return super().available and self.coordinator.device.wifi_status != "offline"
