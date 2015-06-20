"""
homeassistant.components.notify.file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

File notification service.

Configuration:

To use the File notifier you will need to add something like the following
to your config/configuration.yaml

notify:
  platform: file
  filename: FILENAME
  timestamp: 1 or 0

Variables:

filename
*Required
Name of the file to use. The file will be created if it doesn't exist and saved
in your config/ folder.

timestamp
*Required
Add a timestamp to the entry, valid entries are 1 or 0.
"""
import logging
import os

import homeassistant.util.dt as dt_util
from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, ATTR_TITLE, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """ Get the file notification service. """

    if not validate_config(config,
                           {DOMAIN: ['filename',
                                     'timestamp']},
                           _LOGGER):
        return None

    filename = config[DOMAIN]['filename']
    timestamp = config[DOMAIN]['timestamp']

    return FileNotificationService(hass, filename, timestamp)


# pylint: disable=too-few-public-methods
class FileNotificationService(BaseNotificationService):
    """ Implements notification service for the File service. """

    def __init__(self, hass, filename, add_timestamp):
        self.filepath = os.path.join(hass.config.config_dir, filename)
        self.add_timestamp = add_timestamp

    def send_message(self, message="", **kwargs):
        """ Send a message to a file. """

        with open(self.filepath, 'a') as file:
            if os.stat(self.filepath).st_size == 0:
                title = '{} notifications (Log started: {})\n{}\n'.format(
                    kwargs.get(ATTR_TITLE),
                    dt_util.strip_microseconds(dt_util.utcnow()),
                    '-'*80)
                file.write(title)

            if self.add_timestamp == 1:
                text = '{} {}\n'.format(dt_util.utcnow(), message)
                file.write(text)
            else:
                text = '{}\n'.format(message)
                file.write(text)
