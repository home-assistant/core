"""
A component which show the value of temperature, humidity and pressure
from Sense HAT board in the form of service.
Interval time between each reading is a minute by default
but it is configurable from configuration file.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/
"""

import time
import os
from sense_hat import SenseHat

DOMAIN = "sensehat"


def get_cpu_temp():
    """ get CPU temperature """
    res = os.popen("vcgencmd measure_temp").readline()
    t = float(res.replace("temp=", "").replace("'C\n", ""))
    return t


def get_average(x):
    """ use moving average to get better readings """
    if not hasattr(get_average, "t"):
        get_average.t = [x, x, x]
    get_average.t[2] = get_average.t[1]
    get_average.t[1] = get_average.t[0]
    get_average.t[0] = x
    xs = (get_average.t[0]+get_average.t[1]+get_average.t[2])/3
    return xs

sense = SenseHat()
INTERVAL_DEFAULT = 60


def setup(hass, config):
    """ main setup function """
    def get_temp(call):
    """ function for getting sensor values """
        while True:
            t1 = sense.get_temperature_from_humidity()
            t2 = sense.get_temperature_from_pressure()
            t_cpu = get_cpu_temp()
            t = (t1+t2)/2
            temperature_value = t - ((t_cpu-t)/1.5)
            temperature_value = get_average(temperature_value)
            humidity_value = sense.get_humidity()
            pressure_value = sense.get_pressure()
            hass.states.set('sensehat.temperature', round(temperature_value, 2))
            hass.states.set('sensehat.humidity', round(humidity_value, 2))
            hass.states.set('sensehat.pressure', round(pressure_value, 2))
            interval = config[DOMAIN].get('interval', INTERVAL_DEFAULT)
            time.sleep(interval)

    # Register our service with Home Assistant.
    hass.services.register(DOMAIN, 'sensehat_temp', get_temp)

    # Return boolean to indicate that initialization was successfully.
    return True
