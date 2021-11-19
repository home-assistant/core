"""Plugwise Smile Helper Classes."""
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_AWAY,
)
from homeassistant.const import ATTR_ID, ATTR_STATE

from .const import (
    COOLING_ICON,
    FLAME_ICON,
    FLOW_OFF_ICON,
    FLOW_ON_ICON,
    HEATING_ICON,
    IDLE_ICON,
    NO_NOTIFICATION_ICON,
    NOTIFICATION_ICON,
    SEVERITIES,
)


def icon_selector(arg, state):
    """Icon-selection helper function."""
    selector = {
        # Device State icons
        "cooling": COOLING_ICON,
        "dhw-heating": FLAME_ICON,
        "dhw and cooling": COOLING_ICON,
        "dhw and heating": HEATING_ICON,
        "heating": HEATING_ICON,
        "idle": IDLE_ICON,
        # Binary Sensor icons
        "dhw_state": FLOW_ON_ICON if state else FLOW_OFF_ICON,
        "flame_state": FLAME_ICON if state else IDLE_ICON,
        "slave_boiler_state": FLAME_ICON if state else IDLE_ICON,
        "plugwise_notification": NOTIFICATION_ICON if state else NO_NOTIFICATION_ICON,
    }
    return selector.get(arg)


class GWBinarySensor:
    """Represent the Plugwise Smile/Stretch binary_sensor."""

    def __init__(self, data, dev_id, binary_sensor):
        """Initialize the Gateway."""
        self._binary_sensor = binary_sensor
        self._data = data
        self._dev_id = dev_id
        self._attributes = {}
        self._icon = None
        self._is_on = False
        self._notification = {}

    @property
    def extra_state_attributes(self):
        """Gateway binary_sensor extra state attributes."""
        return None if self._attributes == {} else self._attributes

    @property
    def is_on(self):
        """Gateway binary_sensor state."""
        return self._is_on

    @property
    def icon(self):
        """Gateway binary_sensor icon."""
        return self._icon

    @property
    def notification(self):
        """Plugwise Notification message."""
        return self._notification

    def _update_notify(self):
        """Notification update helper."""
        notify = self._data[0]["notifications"]
        self._notification = {}
        for severity in SEVERITIES:
            self._attributes[f"{severity.upper()}_msg"] = []
        if notify != {}:
            for notify_id, details in notify.items():
                for msg_type, msg in details.items():
                    if msg_type not in SEVERITIES:
                        msg_type = "other"  # pragma: no cover

                    self._attributes[f"{msg_type.upper()}_msg"].append(msg)
                    self._notification[notify_id] = f"{msg_type.title()}: {msg}"

    def update_data(self):
        """Handle update callbacks."""
        data = self._data[1][self._dev_id]["binary_sensors"]

        for _, item in enumerate(data):
            if item[ATTR_ID] != self._binary_sensor:
                continue

            self._is_on = item[ATTR_STATE]
            self._icon = icon_selector(self._binary_sensor, self._is_on)

            if self._binary_sensor == "plugwise_notification":
                self._update_notify()


class GWThermostat:
    """Represent a Plugwise Thermostat Device."""

    def __init__(self, data, dev_id):
        """Initialize the Thermostat."""

        self._compressor_state = None
        self._cooling_state = None
        self._data = data
        self._dev_id = dev_id
        self._extra_state_attributes = None
        self._get_presets = None
        self._heating_state = None
        self._hvac_mode = None
        self._last_active_schema = None
        self._preset_mode = None
        self._preset_modes = None
        self._schedule_temp = None
        self._schema_names = None
        self._schema_status = None
        self._selected_schema = None
        self._setpoint = None
        self._smile_class = None
        self._temperature = None

        self._active_device = self._data[0]["active_device"]
        self._heater_id = self._data[0]["heater_id"]
        self._sm_thermostat = self._data[0]["single_master_thermostat"]

    @property
    def compressor_state(self):
        """Compressor state."""
        return self._compressor_state

    @property
    def cooling_state(self):
        """Cooling state."""
        return self._cooling_state

    @property
    def heating_state(self):
        """Heating state."""
        return self._heating_state

    @property
    def hvac_mode(self):
        """Climate active HVAC mode."""
        return self._hvac_mode

    @property
    def presets(self):
        """Climate list of presets."""
        return self._get_presets

    @property
    def preset_mode(self):
        """Climate active preset mode."""
        return self._preset_mode

    @property
    def preset_modes(self):
        """Climate preset modes."""
        return self._preset_modes

    @property
    def last_active_schema(self):
        """Climate last active schema."""
        return self._last_active_schema

    @property
    def current_temperature(self):
        """Climate current measured temperature."""
        return self._temperature

    @property
    def target_temperature(self):
        """Climate target temperature."""
        return self._setpoint

    @property
    def schedule_temperature(self):
        """Climate target temperature."""
        return self._schedule_temp

    @property
    def extra_state_attributes(self):
        """Climate extra state attributes."""
        return self._extra_state_attributes

    def update_data(self):
        """Handle update callbacks."""
        data = self._data[1][self._dev_id]

        # current & target_temps, heater_central data when required
        s_list = data["sensors"]
        for idx, item in enumerate(s_list):
            if item[ATTR_ID] == "temperature":
                self._temperature = s_list[idx][ATTR_STATE]
            if item[ATTR_ID] == "setpoint":
                self._setpoint = s_list[idx][ATTR_STATE]
        self._schedule_temp = data.get("schedule_temperature")
        if self._active_device:
            hc_data = self._data[1][self._heater_id]
            self._compressor_state = hc_data.get("compressor_state")
            if self._sm_thermostat:
                self._cooling_state = hc_data.get("cooling_state")
                self._heating_state = hc_data.get("heating_state")

        # hvac mode
        self._hvac_mode = HVAC_MODE_AUTO
        if "selected_schedule" in data:
            self._selected_schema = data.get("selected_schedule")
            self._schema_status = False
            if self._selected_schema is not None:
                self._schema_status = True

        self._last_active_schema = data.get("last_used")

        if not self._schema_status:
            if self._preset_mode == PRESET_AWAY:
                self._hvac_mode = HVAC_MODE_OFF  # pragma: no cover
            else:
                self._hvac_mode = HVAC_MODE_HEAT
                if self._compressor_state is not None:
                    self._hvac_mode = HVAC_MODE_HEAT_COOL

        # preset modes
        self._get_presets = data.get("presets")
        if self._get_presets:
            self._preset_modes = list(self._get_presets)

        # preset mode
        self._preset_mode = data.get("active_preset")

        # extra state attributes
        attributes = {}
        self._schema_names = data.get("available_schedules")
        self._selected_schema = data.get("selected_schedule")
        if self._schema_names:
            attributes["available_schemas"] = self._schema_names
        if self._selected_schema:
            attributes["selected_schema"] = self._selected_schema
        self._extra_state_attributes = attributes
