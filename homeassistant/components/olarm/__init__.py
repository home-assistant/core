"""The olarm integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN
from .coordinator import OlarmConnectCoordinator

_PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up olarm from a config entry."""
    _LOGGER.debug(
        "Setting up Olarm integration for device: %s", entry.data.get("device_id")
    )

    # use oauth2 to get access token
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    _LOGGER.debug(
        "OAuth2 session created, access_token expires at -> %s",
        session.token["expires_at"],
    )

    try:
        # setup Olarm Connect coordinator
        coordinator = await hass.async_add_executor_job(
            OlarmConnectCoordinator,
            hass,
            entry.data["user_id"],
            entry.data["device_id"],
            session.token["access_token"],
            session,
        )

        # fetch device
        _LOGGER.debug("Fetching device information from Olarm API")
        await coordinator.get_device()

        # connect to MQTT
        _LOGGER.debug("Connecting to Olarm MQTT service")
        await coordinator.init_mqtt()

        # load coordinator into hass.data
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        hass.data[DOMAIN][entry.data["device_id"]] = {"coordinator": coordinator}

        _LOGGER.debug("Setting up platforms for Olarm integration")
        await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    except Exception as e:
        _LOGGER.error("Failed to set up Olarm integration: %s", e)
        # Clean up any partial setup
        if DOMAIN in hass.data and entry.data["device_id"] in hass.data[DOMAIN]:
            coordinator = hass.data[DOMAIN][entry.data["device_id"]].get("coordinator")
            if coordinator:
                try:
                    await coordinator.async_stop()
                except (OSError, ConnectionError, TimeoutError) as cleanup_error:
                    _LOGGER.error("Error during cleanup: %s", cleanup_error)
            hass.data[DOMAIN].pop(entry.data["device_id"], None)
        raise
    else:
        return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN][entry.data["device_id"]]["coordinator"]

    # remove coordinator from hass.data
    hass.data[DOMAIN].pop(entry.data["device_id"], None)

    # stop coordinator
    await coordinator.async_stop()

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
