"""Support for AlarmDecoder sensors (Shows Panel Display)."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import SIGNAL_PANEL_MESSAGE


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> bool:
    """Set up for AlarmDecoder sensor."""

    entity = AlarmDecoderSensor()
    async_add_entities([entity])
    return True


class AlarmDecoderSensor(SensorEntity):
    """Representation of an AlarmDecoder keypad."""

    _attr_icon = "mdi:alarm-check"
    _attr_name = "Alarm Panel Display"
    _attr_should_poll = False

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_PANEL_MESSAGE, self._message_callback
            )
        )

    def _message_callback(self, message):
        if self._attr_native_value != message.text:
            self._attr_native_value = message.text
            self.schedule_update_ha_state()
