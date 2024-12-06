"""The Qbus integration."""

import logging

from qbusmqttapi.factory import QbusMqttTopicFactory

from homeassistant.components.mqtt import async_wait_for_mqtt_client, client as mqtt
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import QbusConfigEntry, QbusDataCoordinator, QbusRuntimeData
from .qbus import QbusConfigContainer

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: QbusConfigEntry) -> bool:
    """Set up Qbus from a config entry."""
    _LOGGER.debug("Loading entry %s", entry.entry_id)

    if not await async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration not available")
        return False

    coordinator = QbusDataCoordinator(hass, entry)
    entry.runtime_data = QbusRuntimeData(coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Subscribe to Qbus config topic
    config_topic = QbusMqttTopicFactory().get_config_topic()
    _LOGGER.debug("Subscribing to %s", config_topic)
    entry.async_on_unload(
        await mqtt.async_subscribe(hass, config_topic, coordinator.config_received)
    )

    # Request Qbus config
    config = await QbusConfigContainer.async_get_or_request_config(hass)

    if config:
        await coordinator.async_update_config(config)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: QbusConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading entry %s", entry.entry_id)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry.runtime_data.coordinator.shutdown()

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: QbusConfigEntry) -> None:
    """Remove a config entry."""
    _LOGGER.debug("Removing entry %s", entry.entry_id)
    entry.runtime_data.coordinator.remove()
