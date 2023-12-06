"""The drop_connect integration."""
from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_DATA_TOPIC, CONF_DEVICE_TYPE, DOMAIN
from .coordinator import DROPDeviceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up DROP from a config entry."""

    # Make sure MQTT integration is enabled and the client is available.
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available")
        return False

    assert config_entry.unique_id is not None
    hass.data.setdefault(DOMAIN, {})[
        config_entry.entry_id
    ] = DROPDeviceDataUpdateCoordinator(hass, config_entry.unique_id)

    # Thin wrapper used to pass MQTT messages to the data coordinator for this entry.
    async def message_received(msg):
        if config_entry.entry_id in hass.data[DOMAIN]:
            await hass.data[DOMAIN][config_entry.entry_id].drop_message_received(
                msg.topic, msg.payload, msg.qos, msg.retain
            )

    # Subscribe to the incoming data topic defined by the config flow using the wrapper defined above.
    _LOGGER.debug(
        "Entry %s (%s) subscribing to %s",
        config_entry.unique_id,
        config_entry.data[CONF_DEVICE_TYPE],
        config_entry.data[CONF_DATA_TOPIC],
    )

    await mqtt.async_subscribe(
        hass, config_entry.data[CONF_DATA_TOPIC], message_received
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)
    return unload_ok
