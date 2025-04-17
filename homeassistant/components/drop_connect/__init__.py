"""The drop_connect integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components import mqtt
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from .const import CONF_DATA_TOPIC, CONF_DEVICE_TYPE
from .coordinator import DROPConfigEntry, DROPDeviceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, config_entry: DROPConfigEntry) -> bool:
    """Set up DROP from a config entry."""

    # Make sure MQTT integration is enabled and the client is available.
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available")
        return False

    if TYPE_CHECKING:
        assert config_entry.unique_id is not None
    drop_data_coordinator = DROPDeviceDataUpdateCoordinator(hass, config_entry)

    @callback
    def mqtt_callback(msg: ReceiveMessage) -> None:
        """Pass MQTT payload to DROP API parser."""
        if drop_data_coordinator.drop_api.parse_drop_message(
            msg.topic, msg.payload, msg.qos, msg.retain
        ):
            drop_data_coordinator.async_set_updated_data(None)

    config_entry.async_on_unload(
        await mqtt.async_subscribe(
            hass, config_entry.data[CONF_DATA_TOPIC], mqtt_callback
        )
    )
    _LOGGER.debug(
        "Entry %s (%s) subscribed to %s",
        config_entry.unique_id,
        config_entry.data[CONF_DEVICE_TYPE],
        config_entry.data[CONF_DATA_TOPIC],
    )

    config_entry.runtime_data = drop_data_coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: DROPConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
