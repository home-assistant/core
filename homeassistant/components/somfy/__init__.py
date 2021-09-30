"""Support for Somfy hubs."""
from datetime import timedelta
import logging

from pymfy.api.devices.category import Category
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_OPTIMISTIC
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
)

from . import api, config_flow
from .const import COORDINATOR, DOMAIN
from .coordinator import SomfyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)
SCAN_INTERVAL_ALL_ASSUMED_STATE = timedelta(minutes=60)

SOMFY_AUTH_CALLBACK_PATH = "/auth/somfy/callback"
SOMFY_AUTH_START = "/auth/somfy"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Inclusive(CONF_CLIENT_ID, "oauth"): cv.string,
                vol.Inclusive(CONF_CLIENT_SECRET, "oauth"): cv.string,
                vol.Optional(CONF_OPTIMISTIC, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["climate", "cover", "sensor", "switch"]


async def async_setup(hass, config):
    """Set up the Somfy component."""
    hass.data[DOMAIN] = {}
    domain_config = config.get(DOMAIN, {})
    hass.data[DOMAIN][CONF_OPTIMISTIC] = domain_config.get(CONF_OPTIMISTIC, False)

    if CONF_CLIENT_ID in domain_config:
        config_flow.SomfyFlowHandler.async_register_implementation(
            hass,
            config_entry_oauth2_flow.LocalOAuth2Implementation(
                hass,
                DOMAIN,
                config[DOMAIN][CONF_CLIENT_ID],
                config[DOMAIN][CONF_CLIENT_SECRET],
                "https://accounts.somfy.com/oauth/oauth/v2/auth",
                "https://accounts.somfy.com/oauth/oauth/v2/token",
            ),
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Somfy from a config entry."""
    # Backwards compat
    if "auth_implementation" not in entry.data:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "auth_implementation": DOMAIN}
        )

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    data = hass.data[DOMAIN]
    coordinator = SomfyDataUpdateCoordinator(
        hass,
        _LOGGER,
        name="somfy device update",
        client=api.ConfigEntrySomfyApi(hass, entry, implementation),
        update_interval=SCAN_INTERVAL,
    )
    data[COORDINATOR] = coordinator

    await coordinator.async_config_entry_first_refresh()

    if all(not bool(device.states) for device in coordinator.data.values()):
        _LOGGER.debug(
            "All devices have assumed state. Update interval has been reduced to: %s",
            SCAN_INTERVAL_ALL_ASSUMED_STATE,
        )
        coordinator.update_interval = SCAN_INTERVAL_ALL_ASSUMED_STATE

    device_registry = await dr.async_get_registry(hass)

    hubs = [
        device
        for device in coordinator.data.values()
        if Category.HUB.value in device.categories
    ]

    for hub in hubs:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, hub.id)},
            manufacturer="Somfy",
            name=hub.name,
            model=hub.type,
        )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
