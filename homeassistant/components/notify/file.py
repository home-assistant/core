"""
homeassistant.components.notify.file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

File notification service.

Configuration:

To use the File notifier you will need to add something like the following
to your config/configuration.yaml

notify:
  platform: file
  path: PATH_TO_FILE
  filename: FILENAME
  timestamp: 1 or 0

Variables:

path
*Required
Path to the directory that contains your file. You need to have write
permission for that directory. The directory will be created if it doesn't
exist.

filename
*Required
Name of the file to use. The file will be created if it doesn't exist.

date
*Required
Add a timestamp to the entry, valid entries are 1 or 0.
"""
import logging
from pathlib import (Path, PurePath)

import homeassistant.util.dt as dt_util
from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, ATTR_TITLE, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """ Get the file notification service. """

    if not validate_config(config,
                           {DOMAIN: ['path',
                                     'filename',
                                     'timestamp']},
                           _LOGGER):
        return None

    path = config[DOMAIN]['path']
    filename = config[DOMAIN]['filename']
    filepath = Path(path, filename)

    # pylint: disable=no-member
    if not filepath.parent.exists():
        try:
            filepath.parent.mkdir(parents=True)
            filepath.touch(mode=0o644, exist_ok=True)
        except:
            _LOGGER.exception("No write permission to given location.")
            # raise PermissionError('') from None
            # raise FileNotFoundError('') from None
            return None

    return FileNotificationService(filepath, config[DOMAIN]['timestamp'])


# pylint: disable=too-few-public-methods
class FileNotificationService(BaseNotificationService):
    """ Implements notification service for the File service. """

    # pylint: disable=no-member
    def __init__(self, filepath, add_timestamp):
        self._filepath = str(PurePath(filepath))
        self._add_timestamp = add_timestamp

    def send_message(self, message="", **kwargs):
        """ Send a message to a file. """

        file = open(self._filepath, 'a')
        if not Path(self._filepath).stat().st_size:
            title = '{} notifications (Log started: {})\n{}\n'.format(
                kwargs.get(ATTR_TITLE),
                dt_util.strip_microseconds(dt_util.utcnow()),
                '-'*80)
            file.write(title)

        if self._add_timestamp == 1:
            text = '{} {}\n'.format(dt_util.utcnow(), message)
            file.write(text)
        else:
            text = '{}\n'.format(message)
            file.write(text)

        file.close()
