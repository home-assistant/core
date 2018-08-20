"""
Support for INSTEON PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_plm/
"""
import asyncio
import logging

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    _LOGGER.warning('The insteon_plm comonent has been replaced by '
                    'the insteon component')
    _LOGGER.warning('Please see https://home-assistant.io/components/insteon')

    return False
