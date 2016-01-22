"""
custom_components.time_from_home
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provide a estimation on how much time you're from home.

Configuration:

To use the time_from_home component you will need to add the following to your
configuration.yaml file.

time_from_home:
"""
import homeassistant.loader as loader
import logging

# The domain of your component. Should be equal to the name of your component
DOMAIN = "time_from_home"

# List of component names (string) your component depends upon
DEPENDENCIES = ['device_tracker']

# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)

def setup(hass, config):
    """ Setup our skeleton component. """

    # States are in the format DOMAIN.OBJECT_ID
    hass.states.set('time_from_home.Hello_World', 'Works!')

    device_tracker = loader.get_component('device_tracker')
    _LOGGER.error("Target entity id %s ", device_tracker.devices)

    # return boolean to indicate that initialization was successful
    return True
