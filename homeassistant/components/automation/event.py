"""
Offer event listening automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#event-trigger
"""
import logging

CONF_EVENT_TYPE = "event_type"
CONF_EVENT_DATA = "event_data"

_LOGGER = logging.getLogger(__name__)


def trigger(hass, config, action):
    """Listen for events based on configuration."""
    event_type = config.get(CONF_EVENT_TYPE)

    if event_type is None:
        _LOGGER.error("Missing configuration key %s", CONF_EVENT_TYPE)
        return False

    event_data = config.get(CONF_EVENT_DATA)

    def handle_event(event):
        """Listen for events and calls the action when data matches."""
        if not event_data or all(val == event.data.get(key) for key, val
                                 in event_data.items()):
            action()

    hass.bus.listen(event_type, handle_event)
    return True
