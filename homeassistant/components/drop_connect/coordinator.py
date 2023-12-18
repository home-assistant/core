"""DROP device data update coordinator object."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING

import attr
from dropmqttapi.mqttapi import DropAPI

from homeassistant.components import mqtt
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_DATA_TOPIC, CONF_DEVICE_TYPE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class DROPDeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """DROP device object."""

    _drop_api: DropAPI | None = None

    def __init__(self, hass: HomeAssistant, unique_id: str) -> None:
        """Initialize the device."""
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}-{unique_id}")
        assert self.config_entry is not None
        self._drop_api = DropAPI()
        self._unsubscribe_callback: Callable[[], None] = attr.ib()
        hass.async_create_task(self.subscribe_mqtt(hass))
        self.config_entry.async_on_unload(self._unsubscribe_callback)

    async def subscribe_mqtt(self, hass: HomeAssistant) -> None:
        """Subscribe to the data topic."""
        assert self.config_entry is not None

        @callback
        def mqtt_callback(msg: ReceiveMessage) -> None:
            """Pass MQTT payload to DROP API parser."""
            if self._drop_api is not None:
                if self._drop_api.parse_drop_message(
                    msg.topic, msg.payload, msg.qos, msg.retain
                ):
                    self.async_set_updated_data(None)

        self._unsubscribe_callback = await mqtt.async_subscribe(
            hass, self.config_entry.data[CONF_DATA_TOPIC], mqtt_callback, 0
        )
        _LOGGER.debug(
            "Entry %s (%s) subscribed to %s",
            self.config_entry.unique_id,
            self.config_entry.data[CONF_DEVICE_TYPE],
            self.config_entry.data[CONF_DATA_TOPIC],
        )

    # Device properties
    @property
    def drop_api(self) -> DropAPI:
        """Return the API instance."""
        if TYPE_CHECKING:
            assert self._drop_api is not None
        return self._drop_api
