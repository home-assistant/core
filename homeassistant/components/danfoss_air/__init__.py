"""Support for Danfoss Air HRV."""
from datetime import timedelta
import logging

from pydanfossair.commands import ReadCommand
from pydanfossair.danfossclient import DanfossClient
import voluptuous as vol

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH]
DOMAIN = "danfoss_air"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_HOST): cv.string})}, extra=vol.ALLOW_EXTRA
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Danfoss Air component."""
    conf = config[DOMAIN]

    hass.data[DOMAIN] = DanfossAir(conf[CONF_HOST])

    for platform in PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    return True


class DanfossAir:
    """Handle all communication with Danfoss Air CCM unit."""

    def __init__(self, host):
        """Initialize the Danfoss Air CCM connection."""
        self._data = {}

        self._client = DanfossClient(host)

    def get_value(self, item):
        """Get value for sensor."""
        return self._data.get(item)

    def update_state(self, command, state_command):
        """Send update command to Danfoss Air CCM."""
        self._data[state_command] = self._client.command(command)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Use the data from Danfoss Air API."""
        _LOGGER.debug("Fetching data from Danfoss Air CCM module")

        self._data[ReadCommand.exhaustTemperature] = self._client.command(
            ReadCommand.exhaustTemperature
        )
        self._data[ReadCommand.outdoorTemperature] = self._client.command(
            ReadCommand.outdoorTemperature
        )
        self._data[ReadCommand.supplyTemperature] = self._client.command(
            ReadCommand.supplyTemperature
        )
        self._data[ReadCommand.extractTemperature] = self._client.command(
            ReadCommand.extractTemperature
        )
        self._data[ReadCommand.humidity] = round(
            self._client.command(ReadCommand.humidity), 2
        )
        self._data[ReadCommand.filterPercent] = round(
            self._client.command(ReadCommand.filterPercent), 2
        )
        self._data[ReadCommand.bypass] = self._client.command(ReadCommand.bypass)
        self._data[ReadCommand.fan_step] = self._client.command(ReadCommand.fan_step)
        self._data[ReadCommand.supply_fan_speed] = self._client.command(
            ReadCommand.supply_fan_speed
        )
        self._data[ReadCommand.exhaust_fan_speed] = self._client.command(
            ReadCommand.exhaust_fan_speed
        )
        self._data[ReadCommand.away_mode] = self._client.command(ReadCommand.away_mode)
        self._data[ReadCommand.boost] = self._client.command(ReadCommand.boost)
        self._data[ReadCommand.battery_percent] = self._client.command(
            ReadCommand.battery_percent
        )
        self._data[ReadCommand.bypass] = self._client.command(ReadCommand.bypass)
        self._data[ReadCommand.automatic_bypass] = self._client.command(
            ReadCommand.automatic_bypass
        )

        _LOGGER.debug("Done fetching data from Danfoss Air CCM module")
