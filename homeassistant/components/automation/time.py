"""
homeassistant.components.automation.time
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Offers time listening automation rules.
"""
from homeassistant.util import convert

CONF_HOURS = "time_hours"
CONF_MINUTES = "time_minutes"
CONF_SECONDS = "time_seconds"


def register(hass, config, action):
    """ Listen for state changes based on `config`. """
    hours = convert(config.get(CONF_HOURS), int)
    minutes = convert(config.get(CONF_MINUTES), int)
    seconds = convert(config.get(CONF_SECONDS), int)

    def time_automation_listener(now):
        """ Listens for time changes and calls action. """
        action()

    hass.track_time_change(
        time_automation_listener,
        hour=hours, minute=minutes, second=seconds)

    return True
