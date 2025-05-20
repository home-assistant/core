import json
import logging


from .const import DOMAIN, GREENCELL_DISC_TOPIC
from .const import GreencellHaAccessLevelEnum as AccessLevel

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import Platform
from homeassistant.components.mqtt import async_subscribe

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the GreenCell integration."""
    setup_reset_msg_listener(hass)
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GreenCell from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    platforms = [Platform.SENSOR, Platform.BUTTON, Platform.NUMBER]
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    setup_reset_msg_listener(hass)
    return True

def setup_reset_msg_listener(hass: HomeAssistant) -> None:
    """Set up a listener for hello/reset messages from devices."""

    @callback
    def handle_hello_message(message):
        """Handle the hello message from a device."""
        try:
            msg = json.loads(message.payload)
            device_id = msg.get('id')

            if not device_id:
                _LOGGER.warning(f'Received message without ID: {msg}')
                return

            known_ids = [
                entry_data.get('serial_number')
                for entry_data in hass.data.get(DOMAIN, {}).values()
            ]

            if device_id in known_ids:
                _LOGGER.info(f'Device {device_id} is already known')
                return

            hass.async_create_task(
                hass.services.async_call(
                    'mqtt',
                    'publish',
                    {
                        'topic': f'/greencell/evse/{device_id}/cmd',
                        'payload': json.dumps({"name": "QUERY"}),
                        'retain': False,
                    }
                )
            )

        except Exception as e:
            _LOGGER.error(f'Error processing hello/reset message: {e}')

    async def mqtt_subscribe():
        """ Wrapper for async_subscribe to handle the subscription."""
        await async_subscribe(hass, GREENCELL_DISC_TOPIC, handle_hello_message)

    hass.async_create_task(mqtt_subscribe())
