"""Anova sous vide cooker integration."""
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add sensors for passed config_entry in HA."""
    async_add_devices([AnovaCookerSensor(config_entry.data["device_id"])])


class AnovaCookerSensor(Entity):
    """Anova Cooker Sensor"""

    def __init__(self, device_id):
        """Set up the device_id, cooker, and empty state & attr."""
        self._device_id = device_id
        self._cooker = None
        self._state = None
        self._attr = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Anova Cooker"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    def update(self):
        """Fetch new state data from the cooker"""
        try:
            if self._cooker is None:
                from anova import AnovaCooker

                self._cooker = AnovaCooker(self._device_id)
            else:
                self._cooker.update_state()
        except:
            pass
        else:
            self._set_attrs()

    def _set_attrs(self):
        self._attr = {
            # 	str 	The status of the current job, for example, PREHEATING.
            "job_status": self._cooker.job_status,
            # int 	The number of seconds remaining in the job.
            "job_time_remaining": self._cooker.job_time_remaining,
            # float 	The heater's percentage duty cycle.
            "heater_duty_cycle": self._cooker.heater_duty_cycle,
            # float 	The motor's percentage duty cycle.
            "motor_duty_cycle": self._cooker.motor_duty_cycle,
            # bool 	The cooker's WiFi connection status.
            "wifi_connected": self._cooker.wifi_connected,
            # str 	The SSID of the network the cooker is connected to.
            "wifi_ssid": self._cooker.wifi_ssid,
            # bool 	Is the device is safe to operate?
            "device_safe": self._cooker.device_safe,
            # bool 	Is there a water leak?
            "water_leak": self._cooker.water_leak,
            # bool 	Is the water level too low for operation?
            "water_level_critical": self._cooker.water_level_critical,
            # bool 	Is the water level low?
            "water_level_low": self._cooker.water_level_low,
            # float 	The heater's temperature in Celsius.
            "heater_temp": self._cooker.heater_temp,
            # float 	The triac's (like a relay) temperature in Celsius.
            "triac_temp": self._cooker.triac_temp,
            # float 	The water's temperature in Celsius.
            "water_temp": self._cooker.water_temp,
        }

        self._state = self._cooker.water_temp

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attr
