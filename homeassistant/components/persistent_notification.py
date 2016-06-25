"""
A component which is collecting configuration errors.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/persistent_notification/
"""

DOMAIN = "persistent_notification"


def create(hass, entity, msg):
    """Create a state for an error."""
    hass.states.set('{}.{}'.format(DOMAIN, entity), msg)


def setup(hass, config):
    """Setup the persistent notification component."""
    return True
