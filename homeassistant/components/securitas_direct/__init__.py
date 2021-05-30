"""The securitas_direct integration."""
from __future__ import annotations

from datetime import timedelta

from pysecuritas.api.alarm import Alarm
from pysecuritas.api.installation import Installation
from pysecuritas.core.session import ConnectionException, Session
from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle

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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up securitas_direct from a config entry."""
    try:
        client = SecuritasClient(entry.data)
        await hass.async_add_executor_job(_connect, client)
    except (ConnectionException, ConnectTimeout, HTTPError):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH},
            data=entry.data,
        )

        return False

    hass.data[DOMAIN] = client
    for platform in SECURITAS_DIRECT_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, SECURITAS_DIRECT_PLATFORMS
    )
    if unload_ok:
        domain = hass.data[DOMAIN]
        domain.logout()
        domain.pop(entry.entry_id)

    return unload_ok


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

    @Throttle(SCAN_INTERVAL)
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
