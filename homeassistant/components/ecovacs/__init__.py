"""Support for Ecovacs Deebot vacuums."""
import logging

from sucks import EcoVacsAPI, VacBot
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_COUNTRY,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_CONTINENT, DOMAIN
from .util import get_client_device_id

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_COUNTRY): vol.All(vol.Lower, cv.string),
                vol.Required(CONF_CONTINENT): vol.All(vol.Lower, cv.string),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [
    Platform.VACUUM,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Ecovacs component."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""

    def get_devices() -> list[VacBot]:
        ecovacs_api = EcoVacsAPI(
            get_client_device_id(),
            entry.data[CONF_USERNAME],
            EcoVacsAPI.md5(entry.data[CONF_PASSWORD]),
            entry.data[CONF_COUNTRY],
            entry.data[CONF_CONTINENT],
        )
        ecovacs_devices = ecovacs_api.devices()

        _LOGGER.debug("Ecobot devices: %s", ecovacs_devices)
        devices: list[VacBot] = []
        for device in ecovacs_devices:
            _LOGGER.debug(
                "Discovered Ecovacs device on account: %s with nickname %s",
                device.get("did"),
                device.get("nick"),
            )
            vacbot = VacBot(
                ecovacs_api.uid,
                ecovacs_api.REALM,
                ecovacs_api.resource,
                ecovacs_api.user_access_token,
                device,
                entry.data[CONF_CONTINENT],
                monitor=True,
            )

            devices.append(vacbot)
        return devices

    hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = await hass.async_add_executor_job(get_devices)

    async def async_stop(event: object) -> None:
        """Shut down open connections to Ecovacs XMPP server."""
        devices: list[VacBot] = hass.data[DOMAIN][entry.entry_id]
        for device in devices:
            _LOGGER.info(
                "Shutting down connection to Ecovacs device %s",
                device.vacuum.get("did"),
            )
            await hass.async_add_executor_job(device.disconnect)

    # Listen for HA stop to disconnect.
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop)

    if hass.data[DOMAIN][entry.entry_id]:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
