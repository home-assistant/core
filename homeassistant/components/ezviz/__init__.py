"""Support for EZVIZ camera."""

import logging

from pyezvizapi.client import EzvizClient
from pyezvizapi.exceptions import (
    EzvizAuthTokenExpired,
    EzvizAuthVerificationCode,
    HTTPError,
    InvalidURL,
    PyEzvizError,
)
import voluptuous as vol

from homeassistant.const import CONF_TIMEOUT, CONF_TYPE, CONF_URL, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_TYPE_CAMERA,
    ATTR_TYPE_CLOUD,
    CONF_FFMPEG_ARGUMENTS,
    CONF_RFSESSION_ID,
    CONF_SCAN_INTERVAL,
    CONF_SESSION_ID,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SERVICE_SET_POLLING_INTERVAL,
)
from .coordinator import EzvizConfigEntry, EzvizDataUpdateCoordinator

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
        Platform.SIREN,
        Platform.SWITCH,
        Platform.UPDATE,
    ],
}


async def async_setup_entry(hass: HomeAssistant, entry: EzvizConfigEntry) -> bool:
    """Set up EZVIZ from a config entry."""
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
            hass,
            entry,
            api=ezviz_client,
            api_timeout=entry.options[CONF_TIMEOUT],
            scan_interval=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        await coordinator.async_config_entry_first_refresh()

        entry.runtime_data = coordinator

        await coordinator.start_mqtt()

    # Check EZVIZ cloud account entity is present, reload cloud account entities for camera entity change to take effect.
    # Cameras are accessed via local RTSP stream with unique credentials per camera.
    # Separate camera entities allow for credential changes per camera.
    if sensor_type == ATTR_TYPE_CAMERA:
        for item in hass.config_entries.async_loaded_entries(domain=DOMAIN):
            if item.data.get(CONF_TYPE) == ATTR_TYPE_CLOUD:
                _LOGGER.debug("Reload Ezviz main account with camera entry")
                await hass.config_entries.async_reload(item.entry_id)
                return True

    await hass.config_entries.async_forward_entry_setups(
        entry, PLATFORMS_BY_TYPE[sensor_type]
    )

    if sensor_type == ATTR_TYPE_CLOUD and not hass.services.has_service(
        DOMAIN, SERVICE_SET_POLLING_INTERVAL
    ):
        async def _handle_set_polling_interval(call: ServiceCall) -> None:
            interval = call.data["interval"]
            duration = call.data["duration"]
            for item in hass.config_entries.async_loaded_entries(domain=DOMAIN):
                if item.data.get(CONF_TYPE) == ATTR_TYPE_CLOUD:
                    coord: EzvizDataUpdateCoordinator = item.runtime_data
                    await coord.set_burst_interval(interval, duration)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_POLLING_INTERVAL,
            _handle_set_polling_interval,
            schema=vol.Schema(
                {
                    vol.Required("interval", default=1): vol.All(
                        cv.positive_int, vol.Range(min=1, max=15)
                    ),
                    vol.Required("duration", default=60): vol.All(
                        cv.positive_int, vol.Range(min=1, max=240)
                    ),
                }
            ),
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EzvizConfigEntry) -> bool:
    """Unload a config entry."""
    sensor_type = entry.data[CONF_TYPE]

    if sensor_type == ATTR_TYPE_CLOUD and hasattr(entry, "runtime_data"):
        coordinator: EzvizDataUpdateCoordinator = entry.runtime_data
        await coordinator.stop_mqtt()

    return await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS_BY_TYPE[sensor_type]
    )
