"""Support for EDP re:dy plugs/switches."""
import logging

from homeassistant.components.edp_redy import EdpRedyDevice, EDP_REDY
from homeassistant.components.switch import SwitchDevice

_LOGGER = logging.getLogger(__name__)

# Load power in watts (W)
ATTR_ACTIVE_POWER = 'active_power'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Perform the setup for re:dy devices."""
    session = hass.data[EDP_REDY]
    devices = []
    for device_pkid, device_json in session.modules_dict.items():
        if "HA_SWITCH" not in device_json["Capabilities"]:
            continue
        devices.append(EdpRedySwitch(session, device_json))

    add_devices(devices)


class EdpRedySwitch(EdpRedyDevice, SwitchDevice):
    """Representation of a Edp re:dy switch (plugs, switches, etc)."""

    def __init__(self, session, device_json):
        """Initialize the switch."""
        EdpRedyDevice.__init__(self, session, device_json['PKID'],
                               device_json['Name'])

        self._active_power = None

        self._parse_data(device_json)

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return 'mdi:power-plug'

    @property
    def is_on(self):
        """Return true if it is on."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._active_power is not None:
            attrs = {ATTR_ACTIVE_POWER: self._active_power}
        else:
            attrs = {}
        attrs.update(super().device_state_attributes)
        return attrs

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        if await self._async_send_state_cmd(True):
            self._state = True
            self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        if await self._async_send_state_cmd(False):
            self._state = False
            self.schedule_update_ha_state()

    async def _async_send_state_cmd(self, state):
        state_json = {"devModuleId": self._id, "key": "RelayState",
                      "value": state}
        return await self._session.async_set_state_var(state_json)

    def _data_updated(self):
        if self._id in self._session.modules_dict:
            device_json = self._session.modules_dict[self._id]
            self._parse_data(device_json)
        else:
            self._is_available = False

        super()._data_updated()

    def _parse_data(self, data):
        """Parse data received from the server."""
        super()._parse_data(data)

        for state_var in data["StateVars"]:
            if state_var["Name"] == "RelayState":
                self._state = True if state_var["Value"] == "true" \
                    else False
            elif state_var["Name"] == "ActivePower":
                try:
                    self._active_power = float(state_var["Value"]) * 1000
                except ValueError:
                    _LOGGER.error("Could not parse power for %s", self._id)
                    self._active_power = None
