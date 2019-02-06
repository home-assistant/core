"""
Support for INSTEON PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_plm/
"""
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the insteon_plm component.

    This component is deprecated as of release 0.77 and should be removed in
    release 0.90.
    """
    _LOGGER.warning('The insteon_plm component has been replaced by '
                    'the insteon component')
    _LOGGER.warning('Please see https://home-assistant.io/components/insteon')

    hass.components.persistent_notification.create(
        'insteon_plm has been replaced by the insteon component.<br />'
        'Please see https://home-assistant.io/components/insteon',
        title='insteon_plm Component Deactivated',
        notification_id='insteon_plm')

    return False
