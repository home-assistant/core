"""Local support for Insteon."""
import logging

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Set up the insteon_local component.

    This component is deprecated as of release 0.77 and should be removed in
    release 0.90.
    """
    _LOGGER.warning('The insteon_local component has been replaced by '
                    'the insteon component')
    _LOGGER.warning('Please see https://home-assistant.io/components/insteon')

    hass.components.persistent_notification.create(
        'insteon_local has been replaced by the insteon component.<br />'
        'Please see https://home-assistant.io/components/insteon',
        title='insteon_local Component Deactivated',
        notification_id='insteon_local')

    return False
