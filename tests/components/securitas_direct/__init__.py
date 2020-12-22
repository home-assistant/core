"""Support for Securitas Direct (AKA Verisure EU) alarm control panels."""

from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import (
    CONF_CODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.helpers import discovery
from homeassistant.util import Throttle
from pysecuritas.api.alarm import Alarm
from pysecuritas.api.installation import Installation
from pysecuritas.core.session import Session

CONF_COUNTRY = "country"
CONF_LANG = "lang"
CONF_INSTALLATION = "installation"
DOMAIN = "securitas_direct"
MIN_SCAN_INTERVAL = timedelta(seconds=20)
DEFAULT_SCAN_INTERVAL = timedelta(seconds=40)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_INSTALLATION): cv.positive_int,
                vol.Optional(CONF_COUNTRY, default="ES"): cv.string,
                vol.Optional(CONF_LANG, default="es"): cv.string,
                vol.Optional(CONF_CODE, default=None): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): (
                    vol.All(cv.time_period, vol.Clamp(min=MIN_SCAN_INTERVAL))
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the Securitas component."""

    securitas_config = config[DOMAIN]
    client = SecuritasClient(securitas_config)
    client.update_overview = Throttle(securitas_config[CONF_SCAN_INTERVAL])(
        client.update_overview
    )
    if not client.login():
        return False

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, lambda event: client.logout())
    client.update_overview()
    for component in ("alarm_control_panel",):
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    hass.data[DOMAIN].client = client

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

        filter = ("1", "2", "31", "32", "46", "202", "311", "13", "24")
        res = self.installation.get_activity_log()
        try:
            regs = res["LIST"]["REG"]
            for reg in regs:
                if reg["@type"] in filter:
                    self.overview = reg

                    return
        except (KeyError, TypeError):
            pass
