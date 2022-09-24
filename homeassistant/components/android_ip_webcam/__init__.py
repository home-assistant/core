"""The Android IP Webcam integration."""
from __future__ import annotations

from pydroid_ipcam import PyDroidIPCam
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_TIMEOUT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_MOTION_SENSOR,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SCAN_INTERVAL,
    SENSORS,
    SWITCHES,
)
from .coordinator import AndroidIPCamDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.SWITCH,
]


CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.All(
                cv.ensure_list,
                [
                    vol.Schema(
                        {
                            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                            vol.Required(CONF_HOST): cv.string,
                            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                            vol.Optional(
                                CONF_TIMEOUT, default=DEFAULT_TIMEOUT
                            ): cv.positive_int,
                            vol.Optional(
                                CONF_SCAN_INTERVAL, default=SCAN_INTERVAL
                            ): cv.time_period,
                            vol.Inclusive(CONF_USERNAME, "authentication"): cv.string,
                            vol.Inclusive(CONF_PASSWORD, "authentication"): cv.string,
                            vol.Optional(CONF_SWITCHES): vol.All(
                                cv.ensure_list, [vol.In(SWITCHES)]
                            ),
                            vol.Optional(CONF_SENSORS): vol.All(
                                cv.ensure_list, [vol.In(SENSORS)]
                            ),
                            vol.Optional(CONF_MOTION_SENSOR): cv.boolean,
                        }
                    )
                ],
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the IP Webcam component."""

    if DOMAIN not in config:
        return True

    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2022.11.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )
    for entry in config[DOMAIN]:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Android IP Webcam from a config entry."""
    websession = async_get_clientsession(hass)
    cam = PyDroidIPCam(
        websession,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
        ssl=False,
    )
    coordinator = AndroidIPCamDataUpdateCoordinator(hass, entry, cam)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
