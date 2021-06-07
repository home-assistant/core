"""Support for the Skybell HD Doorbell."""
from logging import getLogger

from requests.exceptions import ConnectTimeout, HTTPError
from skybellpy import Skybell
from skybellpy.exceptions import SkybellAuthenticationException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
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

PLATFORMS = ["binary_sensor", "camera", "light", "sensor", "switch"]

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        # Deprecated in Home Assistant 2021.7
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


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the SkyBell component."""
    hass.data.setdefault(DOMAIN, {})

    entry_config = {}
    if DOMAIN in config:
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
        None,
        None,
        False,
        False,
        hass.config.path(DEFAULT_CACHEDB),
        True,
        AGENT_IDENTIFIER,
        False,
    )
    try:
        await hass.async_add_executor_job(api.login, email, password, False)
        devices = await hass.async_add_executor_job(api.get_devices)
    except (ConnectTimeout, HTTPError) as err:
        _LOGGER.error("Unable to connect to Skybell service: %s", str(err))
    except SkybellAuthenticationException:
        _LOGGER.error("Authentication Error: please check credentials")

    async def async_update_data():
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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class SkybellDevice(CoordinatorEntity):
    """An HA implementation for Skybell devices."""

    def __init__(self, coordinator, device, _, server_unique_id):
        """Initialize a SkyBell entity."""
        super().__init__(coordinator)
        self._server_unique_id = server_unique_id
        self._device = device
        self._name = device.name
        self._device_class = None

    @property
    def extra_state_attributes(self):
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
    def device_info(self):
        """Return the device information of the entity."""
        info = {
            "identifiers": {(DOMAIN, self._server_unique_id)},
            "manufacturer": DEFAULT_NAME,
            "name": self._name,
            "model": self._device.type,
        }
        return info

    @property
    def device_class(self):
        """Return the class of this device."""
        return self._device_class
