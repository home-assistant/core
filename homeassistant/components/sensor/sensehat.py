"""
A component which show the value of temperature, humidity and pressure from Sense HAT board in the form 
of platform with graphs in history.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/
"""
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from sense_hat import SenseHat
import os


# get CPU temperature
def get_cpu_temp():
  res = os.popen("vcgencmd measure_temp").readline()
  t = float(res.replace("temp=","").replace("'C\n",""))
  return(t)

# use moving average to get better readings
def get_average(x):
  if not hasattr(get_average, "t"):
    get_average.t = [x,x,x]
  get_average.t[2] = get_average.t[1]
  get_average.t[1] = get_average.t[0]
  get_average.t[0] = x
  xs = (get_average.t[0]+get_average.t[1]+get_average.t[2])/3
  return(xs)

sense = SenseHat()
sense.clear()

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    add_devices([SensehatSensor_temperature()])
    add_devices([SensehatSensor_humidity()])
    add_devices([SensehatSensor_pressure()])

class SensehatSensor_temperature(Entity):
    """Representation of a  Temperature Sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Temperature'

    @property
    def state(self):
        t1 = sense.get_temperature_from_humidity()
        t2 = sense.get_temperature_from_pressure()
        t_cpu = get_cpu_temp()
        t = (t1+t2)/2
        t_corr = t - ((t_cpu-t)/1.5)
        t_corr = get_average(t_corr)        
        return t_corr

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

class SensehatSensor_humidity(Entity):
    """Representation of a Humidity Sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Humidity'

    @property
    def state(self):
        humidity = sense.get_humidity()
        return humidity

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return '%'

class SensehatSensor_pressure(Entity):
    """Representation of a Pressure Sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Pressure'

    @property
    def state(self):
        pressure = sense.get_pressure()
        return pressure

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return 'mb'
