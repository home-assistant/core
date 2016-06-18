"""Module to help keep passwords and other secrets.

Depending on availability of the system and existance of the secret,
the secret will be extracted in the following order:
  (1) secrets.yaml: Located in the configuration.yaml directory
  (2) keyring: http://pythonhosted.org/keyring/
"""

import os
import logging
from enum import Enum
try:
    import keyring
except ImportError:
    keyring = None

# Contains source of the secrets resolved by get_secret
# - Used to check missing & unused secrets
# - Can be used to edit secrets through the frontend after HA started
HISTORY = {}
__SECRET_DICT = None

_LOGGER = logging.getLogger(__name__)

_SECRET_NAMESPACE = 'homeassistant'


class SSource(Enum):
    """Source for secrets."""

    notfound = None
    yaml = 1
    keyring = 2


def get_secret(secret_name, log_warning=True):
    """Retrieve a secret from the secrets.yaml or keyring."""
    HISTORY[secret_name] = SSource.notfound

    if __SECRET_DICT and secret_name in __SECRET_DICT:
        HISTORY[secret_name] = SSource.yaml
        _LOGGER.debug('Retrieved from secrets.yaml: %s', secret_name)
        return __SECRET_DICT[secret_name]

    if keyring:
        pwd = keyring.get_password(_SECRET_NAMESPACE, secret_name)
        if pwd:
            HISTORY[secret_name] = SSource.keyring
            _LOGGER.debug('Retrieved from keyring: %s', secret_name)
            return pwd

    if log_warning:
        _LOGGER.warning('Secret not found: %s', secret_name)
    return None


def load_secrets_yaml(config_path, filename='secrets.yaml'):
    """Try to load secrets.yaml."""
    from homeassistant.config import load_yaml_config_file
    from homeassistant.exceptions import HomeAssistantError
    global __SECRET_DICT
    try:
        __SECRET_DICT = load_yaml_config_file(
            os.path.join(os.path.dirname(config_path), filename))
        _LOGGER.info(filename + ' loaded')
        if 'logger' in __SECRET_DICT:
            logger = str(__SECRET_DICT['logger']).lower()
            if logger == 'debug':
                _LOGGER.setLevel(logging.DEBUG)
            del __SECRET_DICT['logger']
    except FileNotFoundError:
        __SECRET_DICT = None
    except HomeAssistantError:
        _LOGGER.error('Could not load %s', filename)
        __SECRET_DICT = None


def check_secrets_on_start(hass):
    """Check secrets on homeassistant startup."""
    def hass_started(event):
        """Callback when hass started."""
        check_secrets(True)
    from homeassistant.const import EVENT_HOMEASSISTANT_START
    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, hass_started)


def check_secrets(log_warning=False):
    """Check for missing or any unused secrets."""
    missing = [sname for sname, ssrc in HISTORY.items()
               if ssrc == SSource.notfound]
    unused = []
    if __SECRET_DICT:
        unused = [sname for sname in __SECRET_DICT
                  if sname not in HISTORY]
    if log_warning:
        if len(unused) > 0:
            _LOGGER.warning('Unused secrets [secrets.yaml]: ' +
                            ', '.join(unused))
        if len(missing) > 0:
            _LOGGER.warning('Missing secrets: ' + ', '.join(missing))
    return {'missing': missing, 'unused': unused}
