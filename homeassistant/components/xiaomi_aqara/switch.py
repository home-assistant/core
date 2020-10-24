"""Support for Xiaomi Aqara binary sensors."""
import logging

from homeassistant.components.switch import SwitchEntity

from . import XiaomiDevice
from .const import DOMAIN, GATEWAYS_KEY

_LOGGER = logging.getLogger(__name__)

# Load power in watts (W)
ATTR_LOAD_POWER = "load_power"

# Total (lifetime) power consumption in watts
ATTR_POWER_CONSUMED = "power_consumed"
ATTR_IN_USE = "in_use"

LOAD_POWER = "load_power"
POWER_CONSUMED = "power_consumed"
ENERGY_CONSUMED = "energy_consumed"
IN_USE = "inuse"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for Xiaomi devices."""
    entities = []
    gateway = hass.data[DOMAIN][GATEWAYS_KEY][config_entry.entry_id]
    for device in gateway.devices["switch"]:
        model = device["model"]
        if model == "plug":
            if "proto" not in device or int(device["proto"][0:1]) == 1:
                data_key = "status"
            else:
                data_key = "channel_0"
            entities.append(
                XiaomiGenericSwitch(
                    device, "Plug", data_key, True, gateway, config_entry
                )
            )
        elif model in [
            "ctrl_neutral1",
            "ctrl_neutral1.aq1",
            "switch_b1lacn02",
            "switch.b1lacn02",
        ]:
            entities.append(
                XiaomiGenericSwitch(
                    device, "Wall Switch", "channel_0", False, gateway, config_entry
                )
            )
        elif model in [
            "ctrl_ln1",
            "ctrl_ln1.aq1",
            "switch_b1nacn02",
            "switch.b1nacn02",
        ]:
            entities.append(
                XiaomiGenericSwitch(
                    device, "Wall Switch LN", "channel_0", False, gateway, config_entry
                )
            )
        elif model in [
            "ctrl_neutral2",
            "ctrl_neutral2.aq1",
            "switch_b2lacn02",
            "switch.b2lacn02",
        ]:
            entities.append(
                XiaomiGenericSwitch(
                    device,
                    "Wall Switch Left",
                    "channel_0",
                    False,
                    gateway,
                    config_entry,
                )
            )
            entities.append(
                XiaomiGenericSwitch(
                    device,
                    "Wall Switch Right",
                    "channel_1",
                    False,
                    gateway,
                    config_entry,
                )
            )
        elif model in [
            "ctrl_ln2",
            "ctrl_ln2.aq1",
            "switch_b2nacn02",
            "switch.b2nacn02",
        ]:
            entities.append(
                XiaomiGenericSwitch(
                    device,
                    "Wall Switch LN Left",
                    "channel_0",
                    False,
                    gateway,
                    config_entry,
                )
            )
            entities.append(
                XiaomiGenericSwitch(
                    device,
                    "Wall Switch LN Right",
                    "channel_1",
                    False,
                    gateway,
                    config_entry,
                )
            )
        elif model in ["86plug", "ctrl_86plug", "ctrl_86plug.aq1"]:
            if "proto" not in device or int(device["proto"][0:1]) == 1:
                data_key = "status"
            else:
                data_key = "channel_0"
            entities.append(
                XiaomiGenericSwitch(
                    device, "Wall Plug", data_key, True, gateway, config_entry
                )
            )
    async_add_entities(entities)


class XiaomiGenericSwitch(XiaomiDevice, SwitchEntity):
    """Representation of a XiaomiPlug."""

    def __init__(
        self,
        device,
        name,
        data_key,
        supports_power_consumption,
        xiaomi_hub,
        config_entry,
    ):
        """Initialize the XiaomiPlug."""
        self._data_key = data_key
        self._in_use = None
        self._load_power = None
        self._power_consumed = None
        self._supports_power_consumption = supports_power_consumption
        super().__init__(device, name, xiaomi_hub, config_entry)

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if self._data_key == "status":
            return "mdi:power-plug"
        return "mdi:power-socket"

    @property
    def is_on(self):
        """Return true if it is on."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._supports_power_consumption:
            attrs = {
                ATTR_IN_USE: self._in_use,
                ATTR_LOAD_POWER: self._load_power,
                ATTR_POWER_CONSUMED: self._power_consumed,
            }
        else:
            attrs = {}
        attrs.update(super().device_state_attributes)
        return attrs

    @property
    def should_poll(self):
        """Return the polling state. Polling needed for Zigbee plug only."""
        return self._supports_power_consumption

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if self._write_to_hub(self._sid, **{self._data_key: "on"}):
            self._state = True
            self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if self._write_to_hub(self._sid, **{self._data_key: "off"}):
            self._state = False
            self.schedule_update_ha_state()

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        if IN_USE in data:
            self._in_use = int(data[IN_USE])
            if not self._in_use:
                self._load_power = 0

        for key in [POWER_CONSUMED, ENERGY_CONSUMED]:
            if key in data:
                self._power_consumed = round(float(data[key]), 2)
                break

        if LOAD_POWER in data:
            self._load_power = round(float(data[LOAD_POWER]), 2)

        value = data.get(self._data_key)
        if value not in ["on", "off"]:
            return False

        state = value == "on"
        if self._state == state:
            return False
        self._state = state
        return True

    def update(self):
        """Get data from hub."""
        _LOGGER.debug("Update data from hub: %s", self._name)
        self._get_from_hub(self._sid)
