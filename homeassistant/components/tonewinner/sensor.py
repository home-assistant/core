import serial_asyncio

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import *


async def async_setup_entry(hass, config_entry, async_add_entities):
    data = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([TonewinnerSensor(hass, config_entry, data)])


class TonewinnerSensor(SensorEntity):
    def __init__(self, hass, entry, data):
        self._attr_name = "Receiver Connection"
        self._attr_unique_id = f"{entry.entry_id}_conn"
        self.port = data[CONF_SERIAL_PORT]
        self.baud = data[CONF_BAUD_RATE]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Tonewinner",
            model="AT-500",
        )

    async def async_update(self):
        # Simple ping: open port, close it, report "OK"
        try:
            _, proto = await serial_asyncio.create_serial_connection(
                asyncio.get_event_loop(),
                lambda: asyncio.Protocol(),
                self.port,
                self.baud,
                timeout=1,
            )
            transport, _ = await asyncio.wait_for(
                serial_asyncio.connection_for_serial(
                    loop=asyncio.get_event_loop(),
                    protocol_factory=lambda: asyncio.Protocol,
                    url=self.port,
                    baudrate=self.baud,
                ),
                timeout=1,
            )
            transport.close()
            self._attr_native_value = "OK"
        except Exception as e:
            self._attr_native_value = f"Error: {e}"
