"""
homeassistant.components.notify.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Demo notification service.
"""
from homeassistant.components.notify import ATTR_TITLE, BaseNotificationService


EVENT_NOTIFY = "notify"


def get_service(hass, config):
    """ Get the demo notification service. """

    return DemoNotificationService(hass)


# pylint: disable=too-few-public-methods
class DemoNotificationService(BaseNotificationService):
    """ Implements demo notification service. """

    def __init__(self, hass):
        self.hass = hass

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        title = kwargs.get(ATTR_TITLE)

        self.hass.bus.fire(EVENT_NOTIFY, {"title": title, "message": message})
