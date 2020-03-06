"""Support for IKEA Tradfri sensors."""

from homeassistant.const import DEVICE_CLASS_BATTERY, UNIT_PERCENTAGE

from .base_class import TradfriBaseDevice
from .const import CONF_GATEWAY_ID, KEY_API, KEY_GATEWAY


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Tradfri config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    api = hass.data[KEY_API][config_entry.entry_id]
    gateway = hass.data[KEY_GATEWAY][config_entry.entry_id]

    devices_commands = await api(gateway.get_devices())
    all_devices = await api(devices_commands)
    devices = (
        dev
        for dev in all_devices
        if not dev.has_light_control
        and not dev.has_socket_control
        and not dev.has_blind_control
        and not dev.has_signal_repeater_control
    )
    if devices:
        async_add_entities(TradfriSensor(device, api, gateway_id) for device in devices)


class TradfriSensor(TradfriBaseDevice):
    """The platform class required by Home Assistant."""

    def __init__(self, device, api, gateway_id):
        """Initialize the device."""
        super().__init__(device, api, gateway_id)
        self._unique_id = f"{gateway_id}-{device.id}"

    @property
    def device_class(self):
        """Return the devices' state attributes."""
        return DEVICE_CLASS_BATTERY

    @property
    def state(self):
        """Return the current state of the device."""
        return self._device.device_info.battery_level

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return UNIT_PERCENTAGE
