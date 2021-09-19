"""Support for the Skybell HD Doorbell."""
from __future__ import annotations

from logging import getLogger
from typing import Any

from requests.exceptions import ConnectTimeout, HTTPError
from skybellpy import Skybell
from skybellpy.device import SkybellDevice
from skybellpy.exceptions import SkybellAuthenticationException
import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.camera import DOMAIN as CAMERA
from homeassistant.components.light import DOMAIN as LIGHT
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.switch import DOMAIN as SWITCH
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    AGENT_IDENTIFIER,
    ATTRIBUTION,
    DATA_COORDINATOR,
    DATA_DEVICES,
    DEFAULT_CACHEDB,
    DEFAULT_NAME,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
)

_LOGGER = getLogger(__name__)

PLATFORMS = [BINARY_SENSOR, CAMERA, LIGHT, SENSOR, SWITCH]

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        # Deprecated in Home Assistant 2021.10
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
        cache_path=hass.config.path(DEFAULT_CACHEDB),
        agent_identifier=AGENT_IDENTIFIER,
    )
    try:
        await hass.async_add_executor_job(api.login, email, password, False)
        devices = await hass.async_add_executor_job(api.get_devices)
    except (ConnectTimeout, HTTPError) as ex:
        raise ConfigEntryNotReady(f"Unable to connect to Skybell service: {ex}") from ex
    except SkybellAuthenticationException as ex:
        raise ConfigEntryAuthFailed(
            f"Authentication Error: please check credentials: {ex}"
        ) from ex

    async def async_update_data() -> None:
        """Fetch data from API endpoint."""
        try:
            for device in devices:
                await hass.async_add_executor_job(device.refresh)
        except (ConnectTimeout, HTTPError) as err:
            raise UpdateFailed(f"Failed to communicating with device {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DEFAULT_NAME,
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_DEVICES: devices,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class SkybellEntity(CoordinatorEntity):
    """An HA implementation for Skybell devices."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: SkybellDevice,
        _: Any,
        server_unique_id: str,
    ) -> None:
        """Initialize a SkyBell entity."""
        super().__init__(coordinator)
        self._device = device
        self._attr_device_info = {
            ATTR_IDENTIFIERS: {
                (DOMAIN, f"{server_unique_id}-{device._info_json.get('serialNo')}")
            },
            "connections": {(dr.CONNECTION_NETWORK_MAC, device._info_json.get("mac"))},
            ATTR_MANUFACTURER: DEFAULT_NAME,
            ATTR_MODEL: device.type,
            ATTR_NAME: device.name,
            ATTR_SW_VERSION: device._info_json.get("firmwareVersion"),
        }

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device_id": self._device.device_id,
            "status": self._device.status,
            "location": self._device.location,
            "wifi_ssid": self._device.wifi_ssid,
            "wifi_status": self._device.wifi_status,
            "last_check_in": self._device.last_check_in,
            "motion_threshold": self._device.motion_threshold,
            "video_profile": self._device.video_profile,
        }

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self._device.wifi_status != "offline"
