"""The Homee integration."""

import logging

from pyHomee import Homee, HomeeAuthFailedException, HomeeConnectionFailedException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.COVER]

type HomeeConfigEntry = ConfigEntry[Homee]


async def async_setup_entry(hass: HomeAssistant, entry: HomeeConfigEntry) -> bool:
    """Set up homee from a config entry."""
    # Create the Homee api object using host, user,
    # password & pyHomee instance from the config
    homee = Homee(
        host=entry.data[CONF_HOST],
        user=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        device="HA_" + hass.config.location_name,
        reconnect_interval=10,
        max_retries=100,
    )

    # Start the homee websocket connection as a new task
    # and wait until we are connected
    try:
        await homee.get_access_token()
    except HomeeConnectionFailedException as exc:
        raise ConfigEntryNotReady(
            f"Connection to Homee failed: {exc.__cause__}"
        ) from exc
    except HomeeAuthFailedException as exc:
        raise ConfigEntryNotReady(
            f"Authentication to Homee failed: {exc.__cause__}"
        ) from exc

    hass.loop.create_task(homee.run())
    await homee.wait_until_connected()

    entry.runtime_data = homee
    entry.async_on_unload(homee.disconnect)

    async def _connection_update_callback(connected: bool) -> None:
        """Call when the device is notified of changes."""
        if connected:
            _LOGGER.warning("Reconnected to Homee at %s", entry.data[CONF_HOST])
        else:
            _LOGGER.warning("Disconnected from Homee at %s", entry.data[CONF_HOST])

    await homee.add_connection_listener(_connection_update_callback)

    # create device register entry
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={
            (dr.CONNECTION_NETWORK_MAC, dr.format_mac(homee.settings.mac_address))
        },
        identifiers={(DOMAIN, homee.settings.uid)},
        manufacturer="homee",
        name=homee.settings.homee_name,
        model="homee",
        sw_version=homee.settings.version,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomeeConfigEntry) -> bool:
    """Unload a homee config entry."""
    # Unload platforms
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
