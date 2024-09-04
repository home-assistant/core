"""Support for AlarmDecoder sensors (Shows Panel Display)."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AlarmDecoderConfigEntry
from .const import SIGNAL_PANEL_MESSAGE
from .entity import AlarmDecoderEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlarmDecoderConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up for AlarmDecoder sensor."""

    entity = AlarmDecoderSensor(client=entry.runtime_data.client)
    async_add_entities([entity])


class AlarmDecoderSensor(AlarmDecoderEntity, SensorEntity):
    """Representation of an AlarmDecoder keypad."""

    _attr_translation_key = "alarm_panel_display"
    _attr_name = "Alarm Panel Display"
    _attr_should_poll = False

    def __init__(self, client):
        """Initialize the alarm decoder sensor."""
        super().__init__(client)
        self._attr_unique_id = f"{client.serial_number}-display"

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_PANEL_MESSAGE, self._message_callback
            )
        )

    def _message_callback(self, message):
        if self._attr_native_value != message.text:
            self._attr_native_value = message.text
            self.schedule_update_ha_state()
