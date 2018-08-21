"""
Local support for Insteon.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_local/
"""
import logging

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup the insteon_local component."""
    _LOGGER.warning('The insteon_local comonent has been replaced by '
                    'the insteon component')
    _LOGGER.warning('Please see https://home-assistant.io/components/insteon')

    return False
