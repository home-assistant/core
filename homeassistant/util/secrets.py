"""Module to help keep passwords and other secrets."""

import os
import logging
import collections
from enum import Enum
from homeassistant.config import load_yaml_config_file
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import EVENT_HOMEASSISTANT_START
try:
    import keyring  # pylint: disable=wrong-import-order,wrong-import-position
except ImportError:
    keyring = None

# Contains secrets resolved by get_secret (from config files & components)
# History can be used to edit secrets through the frontend after HA started.
HISTORY = {}
"""HISTORY will be used to store secrets extracted from the configuration files
and make it available for editing later."""  # pylint: disable=W0105
SECRET_PLACEHOLDER = '(-)'
SECRET_DICT = None
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)


class SSource(Enum):
    """Source for secrets."""

    yaml = 1
    keyring = 2


def get_secret(namespace, username):
    """Retrieve a secret from the secrets.yaml or keyring.

    The full secret path will be: namespace/username

    Once retrieved, the source will be saved in the HISTORY

    Depending on availability of the system and existance of the secret's path,
    the secret will be extracted in the following order:
      (1) secrets.yaml: Located in the configuration.yaml directory
          Format: /path/to/username: secret
      (2) keyring: http://pythonhosted.org/keyring/
    """
    fullpath = (str(namespace) + '/' + str(username)).replace(' ', '_')

    global HISTORY  # pylint: disable=global-variable-not-assigned
    HISTORY[fullpath] = None

    if SECRET_DICT:
        try:
            HISTORY[fullpath] = (SECRET_DICT[fullpath], SSource.yaml)
            _LOGGER.debug('from secrets.yaml: %s [%s]', fullpath,
                          SECRET_DICT[fullpath])
            return HISTORY[fullpath][0]
        except (TypeError, IndexError, KeyError):
            pass

    if keyring:
        pwd = keyring.get_password(namespace, username)
        if pwd:
            HISTORY[fullpath] = (pwd, SSource.keyring)
            _LOGGER.debug('from keyring: %s [%s]', fullpath, pwd)
            return HISTORY[fullpath][0]

    _LOGGER.warning('Secret not found: %s', fullpath)
    return None


def load_secrets_config_file(config_path, filename='secrets.yaml'):
    """Try to load secrets.yaml."""
    global SECRET_DICT
    try:
        SECRET_DICT = load_yaml_config_file(
            os.path.join(os.path.dirname(config_path), filename))
        _LOGGER.info(filename + ' loaded')
    except FileNotFoundError:
        SECRET_DICT = None
    except HomeAssistantError:
        _LOGGER.error('Could not load %s', filename)
        SECRET_DICT = None


def decode(config_dict, config_path=None, hass=None):
    """Decode secrets contained in the config_dict using get_password."""
    if config_path:
        load_secrets_config_file(config_path)
    if keyring:
        _LOGGER.info('keyring active')
    if not SECRET_DICT and not keyring:
        _LOGGER.info('Secrets not protected')
        return config_dict

    def iterate(cdict, path):
        """Iterate over the dictionary and populate secrets."""
        for key, value in cdict.items():
            new_path = path + '/' + key
            if isinstance(value, collections.OrderedDict):
                iterate(value, new_path)
            elif isinstance(value, list):
                # Process items in lists, might be too deep?
                for val in value:
                    iterate(val, new_path)
            elif isinstance(value, str):
                # Expand properties containing the placeholder
                if value == SECRET_PLACEHOLDER:
                    cdict[key] = get_secret(path, key)
                    _LOGGER.debug('%s = %s', new_path, cdict[key])
                # Special handling for password if username found
                if key == 'username' and 'password' not in cdict:
                    cdict['password'] = get_secret(path, 'password')
                    _LOGGER.debug('%s/password = %s', path, cdict['password'])

    iterate(config_dict, '')

    if hass:
        hass.bus.listen_once(EVENT_HOMEASSISTANT_START,
                             lambda event: check_stale_secrets())
    return config_dict


def check_stale_secrets():
    """Check is SECRET_DICT contains unused secrets."""
    if not SECRET_DICT:
        return
    stale = []
    for key in SECRET_DICT.keys():
        if key not in HISTORY:
            stale.append(key)
    if len(stale) > 0:
        _LOGGER.warning('Stale secrets: ' + ', '.join(stale))
