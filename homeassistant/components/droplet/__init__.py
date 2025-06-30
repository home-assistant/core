"""The Droplet integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components import mqtt
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_DATA_TOPIC, CONF_HEALTH_TOPIC, DOMAIN
from .coordinator import DropletConfigEntry, DropletDataCoordinator
from .services import handle_flow_rate

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: DropletConfigEntry
) -> bool:
    """Set up Droplet from a config entry."""

    # Make sure MQTT integration is enabled and the client is available.
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available")
        raise ConfigEntryNotReady("Device is offline")

    if TYPE_CHECKING:
        assert config_entry.unique_id is not None
    droplet_coordinator = DropletDataCoordinator(hass, config_entry)

    @callback
    def mqtt_callback(msg: ReceiveMessage) -> None:
        """Pass MQTT payload to Droplet API parser."""
        if droplet_coordinator.droplet.parse_message(
            msg.topic, msg.payload, msg.qos, msg.retain
        ):
            droplet_coordinator.async_set_updated_data(None)

    for topic in (CONF_DATA_TOPIC, CONF_HEALTH_TOPIC):
        config_entry.async_on_unload(
            await mqtt.async_subscribe(hass, config_entry.data[topic], mqtt_callback)
        )

    config_entry.runtime_data = droplet_coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    hass.services.async_register(DOMAIN, "hello", handle_flow_rate)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: DropletConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
