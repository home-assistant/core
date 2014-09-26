"""
custom_components.example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Bare minimum what is needed for a component to be valid.
"""

# The domain of your component. Should be equal to the name of your component
DOMAIN = "example"

# List of component names (string) your component depends upon
# If you are setting up a group but not using a group for anything, don't depend on group
DEPENDENCIES = []

# pylint: disable=unused-argument
def setup(hass, config):
    """ Register services or listen for events that your component needs. """

    # Example of a service that prints the service call to the command-line.
    hass.services.register(DOMAIN, "example_service_name", print)

    # This prints a time change event to the command-line twice a minute.
    hass.track_time_change(print, second=[0, 30])

    # See also (defined in homeassistant/__init__.py):
    # hass.track_state_change
    # hass.track_point_in_time

    # Tells the bootstrapper that the component was succesfully initialized
    return True
