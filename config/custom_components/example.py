"""
custom_components.example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Bare minimum what is needed for a component to be valid.
"""

DOMAIN = "example"
DEPENDENCIES = []

# pylint: disable=unused-argument
def setup(hass, config):
    """ Register services or listen for events that your component needs. """

    # Example of a service that prints the service call to the command-line.
    hass.services.register(DOMAIN, "service_name", print)

    # This prints a time change event to the command-line twice a minute.
    hass.track_time_change(print, second=[0, 30])

    # See also:
    # hass.track_state_change
    # hass.track_point_in_time

    return True
