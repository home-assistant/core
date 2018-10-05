"""Define constants for the SimpliSafe component."""
import logging

LOGGER = logging.getLogger('homeassistant.components.simplisafe')

DOMAIN = 'simplisafe'

DATA_CLIENT = 'client'
DATA_FILE_SCAFFOLD = '.simplisafe_{0}'
DATA_LISTENER = 'listener'

TOPIC_UPDATE = 'update_{0}'
