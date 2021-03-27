"""Support for Securitas Direct (AKA Verisure EU) alarm control panels."""
from copy import deepcopy
from datetime import timedelta

from pysecuritas.api.alarm import Alarm
from pysecuritas.api.installation import Installation
from pysecuritas.core.session import ConnectionException, Session
from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.util import Throttle

from ...config_entries import SOURCE_IMPORT, SOURCE_REAUTH
from .const import (
    CONF_COUNTRY,
    CONF_INSTALLATION,
    CONF_LANG,
    DOMAIN,
    SECURITAS_DIRECT_PLATFORMS,
)

SCAN_INTERVAL = timedelta(seconds=60)


def _connect(client):
    """Connect to securitas."""

    client.login()

    return True


async def async_setup(hass, config) -> bool:
    """Set up securitas direct."""

    return True


async def async_setup_entry(hass, config_entry):
    """Set up securitas direct entry."""

    try:
        client = SecuritasClient(config_entry.data)
        client.update_overview = Throttle(SCAN_INTERVAL)(client.update_overview)
        await hass.async_add_executor_job(_connect, client)
    except (ConnectionException, ConnectTimeout, HTTPError):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH},
            data=config_entry.data,
        )

        return False

    hass.data[DOMAIN] = client
    for platform in SECURITAS_DIRECT_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""

    hass.data[DOMAIN].logout()
    hass.data.pop(DOMAIN)

    return True


class SecuritasClient:
    """A Securitas hub wrapper class."""

    def __init__(self, config):
        """Initialize the Securitas hub."""
        self.overview = {}
        self.code = config.get(CONF_CODE)
        self.installation_num = config[CONF_INSTALLATION]
        self.session = Session(
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            self.installation_num,
            config[CONF_COUNTRY].upper(),
            config[CONF_LANG].lower(),
        )
        self.installation = Installation(self.session)
        self.alarm = Alarm(self.session)
        self.installation_num = config[CONF_INSTALLATION]
        self.installation_alias = None

    def login(self):
        """Login to Securitas."""
        self.session.connect()
        self.installation_alias = self.installation.get_alias()

        return self.session.is_connected()

    def logout(self):
        """Logout from Securitas."""
        self.session.close()

        return True

    def update_overview(self):
        """Update the overview."""

        state_types = ("1", "2", "31", "32", "46", "202", "311", "13", "24")
        res = self.installation.get_activity_log()
        try:
            regs = res["LIST"]["REG"]
            for reg in regs:
                if reg["@type"] in state_types:
                    self.overview = reg

                    return
        except (KeyError, TypeError):
            pass
