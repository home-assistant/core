import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .synapse.bridge import SynapseBridge

class SynapseHealthSensor(BinarySensorEntity):
    def __init__(
        self,
        bridge: SynapseBridge,
        hass: HomeAssistant
    ):
        self.logger = logging.getLogger(__name__)
        self.hass = hass
        self.bridge = bridge
        self.async_on_remove(
            self.hass.bus.async_listen(
                self.bridge.event_name("health"),
                self._handle_availability_update,
            )
        )

    @property
    def device_info(self) -> DeviceInfo:
        return self.bridge.primary_device

    @property
    def icon(self):
        if self.bridge.online:
            return "mdi:server"
        return "mdi:server-outline"

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    @property
    def name(self):
        return f"{self.bridge.app_data.get("title")} Online"

    @property
    def unique_id(self):
        return f"{self.bridge.app_data.get("unique_id")}-online"

    @property
    def is_on(self):
        return self.bridge.online

    @callback
    async def _handle_availability_update(self, event):
        """Handle health status update."""
        self.async_schedule_update_ha_state(True)
