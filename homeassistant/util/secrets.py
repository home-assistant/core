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
SECRET_DICT = None

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

    if SECRET_DICT and secret_name in SECRET_DICT:
        HISTORY[secret_name] = SSource.yaml
        _LOGGER.debug('from secrets.yaml: %s = "%s"', secret_name,
                      SECRET_DICT[secret_name])
        return SECRET_DICT[secret_name]

    if keyring:
        pwd = keyring.get_password(_SECRET_NAMESPACE, secret_name)
        if pwd:
            HISTORY[secret_name] = SSource.keyring
            _LOGGER.debug('from keyring: %s = "%s"', secret_name, pwd)
            return pwd

    if log_warning:
        _LOGGER.warning('Secret not found: %s', secret_name)
    return None


def load_secrets_yaml(config_path, filename='secrets.yaml'):
    """Try to load secrets.yaml."""
    from homeassistant.config import load_yaml_config_file
    from homeassistant.exceptions import HomeAssistantError
    global SECRET_DICT
    try:
        SECRET_DICT = load_yaml_config_file(
            os.path.join(os.path.dirname(config_path), filename))
        _LOGGER.info(filename + ' loaded')
        if 'debug' in SECRET_DICT and SECRET_DICT['debug']:
            _LOGGER.setLevel(logging.DEBUG)
    except FileNotFoundError:
        SECRET_DICT = None
    except HomeAssistantError:
        _LOGGER.error('Could not load %s', filename)
        SECRET_DICT = None


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
    if SECRET_DICT:
        unused = [sname for sname in SECRET_DICT.keys()
                  if sname not in HISTORY and sname != 'debug']
    if log_warning:
        if len(unused) > 0:
            _LOGGER.warning('Unused secrets [secrets.yaml]: ' +
                            ', '.join(unused))
        if len(missing) > 0:
            _LOGGER.warning('Missing secrets: ' + ', '.join(missing))
    return {'missing': missing, 'unused': unused}


def _cmd_line():
    """Set / Get secrets through cmdline."""
    if not keyring:
        _LOGGER.error("keyring needs to be installed (pip install keyring)")
        return
    import argparse
    parser = argparse.ArgumentParser(
        description="Manage secrets in the keyring.",
        epilog="Alternative use: keyring [set|get|del] homeassistant name")
    parser.add_argument('action', help="The action [get|set|del]")
    parser.add_argument('name', help="The name of the secret")
    arguments = parser.parse_args()
    if arguments.action == 'set':
        from getpass import getpass
        secret = getpass("Secret for '{}': ".format(arguments.name))
        if isinstance(secret, str) and len(secret) > 0:
            keyring.set_password(_SECRET_NAMESPACE, arguments.name, secret)
        else:
            print("Not set")
    elif arguments.action == 'del':
        try:
            keyring.delete_password(_SECRET_NAMESPACE, arguments.name)
        except keyring.errors.PasswordDeleteError:
            print("Secret not found.")
    elif arguments.action == 'get':
        print(keyring.get_password(_SECRET_NAMESPACE, arguments.name))
    else:
        print('Invalid action: {}'.format(arguments.action))

if __name__ == "__main__":
    _cmd_line()
