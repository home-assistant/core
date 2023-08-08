"""Support for EZVIZ camera."""
import logging

from pyezviz.client import EzvizClient
from pyezviz.exceptions import (
    EzvizAuthTokenExpired,
    EzvizAuthVerificationCode,
    HTTPError,
    InvalidURL,
    PyEzvizError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TIMEOUT, CONF_TYPE, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import (
    ATTR_TYPE_CAMERA,
    ATTR_TYPE_CLOUD,
    CONF_FFMPEG_ARGUMENTS,
    CONF_RFSESSION_ID,
    CONF_SESSION_ID,
    DATA_COORDINATOR,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .coordinator import EzvizDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS_BY_TYPE: dict[str, list] = {
    ATTR_TYPE_CAMERA: [],
    ATTR_TYPE_CLOUD: [
        Platform.ALARM_CONTROL_PANEL,
        Platform.BINARY_SENSOR,
        Platform.BUTTON,
        Platform.CAMERA,
        Platform.IMAGE,
        Platform.LIGHT,
        Platform.NUMBER,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
        Platform.UPDATE,
    ],
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EZVIZ from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    sensor_type: str = entry.data[CONF_TYPE]
    ezviz_client = None

    if not entry.options:
        options = {
            CONF_FFMPEG_ARGUMENTS: DEFAULT_FFMPEG_ARGUMENTS,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        }

        hass.config_entries.async_update_entry(entry, options=options)

    # Initialize EZVIZ cloud entities
    if PLATFORMS_BY_TYPE[sensor_type]:
        # Initiate reauth config flow if account token if not present.
        if not entry.data.get(CONF_SESSION_ID):
            raise ConfigEntryAuthFailed

        ezviz_client = EzvizClient(
            token={
                CONF_SESSION_ID: entry.data.get(CONF_SESSION_ID),
                CONF_RFSESSION_ID: entry.data.get(CONF_RFSESSION_ID),
                "api_url": entry.data.get(CONF_URL),
            },
            timeout=entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        )

        try:
            await hass.async_add_executor_job(ezviz_client.login)

        except (EzvizAuthTokenExpired, EzvizAuthVerificationCode) as error:
            raise ConfigEntryAuthFailed from error

        except (InvalidURL, HTTPError, PyEzvizError) as error:
            _LOGGER.error("Unable to connect to Ezviz service: %s", str(error))
            raise ConfigEntryNotReady from error

        coordinator = EzvizDataUpdateCoordinator(
            hass, api=ezviz_client, api_timeout=entry.options[CONF_TIMEOUT]
        )

        await coordinator.async_config_entry_first_refresh()

        hass.data[DOMAIN][entry.entry_id] = {DATA_COORDINATOR: coordinator}

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Check EZVIZ cloud account entity is present, reload cloud account entities for camera entity change to take effect.
    # Cameras are accessed via local RTSP stream with unique credentials per camera.
    # Separate camera entities allow for credential changes per camera.
    if sensor_type == ATTR_TYPE_CAMERA and hass.data[DOMAIN]:
        for item in hass.config_entries.async_entries(domain=DOMAIN):
            if item.data.get(CONF_TYPE) == ATTR_TYPE_CLOUD:
                _LOGGER.info("Reload Ezviz main account with camera entry")
                await hass.config_entries.async_reload(item.entry_id)
                return True

    await hass.config_entries.async_forward_entry_setups(
        entry, PLATFORMS_BY_TYPE[sensor_type]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    sensor_type = entry.data[CONF_TYPE]

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS_BY_TYPE[sensor_type]
    )
    if sensor_type == ATTR_TYPE_CLOUD and unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
