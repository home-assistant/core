"""Support for Danfoss Air HRV."""

from datetime import datetime, timedelta
import logging
import threading

import probatio
from pydanfossair.commands import ReadCommand
from pydanfossair.danfossclient import DanfossClient

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, INTEGRATION_TITLE

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONFIG_SCHEMA = probatio.Schema(
    {DOMAIN: probatio.Schema({probatio.Required(CONF_HOST): cv.string})},
    extra=probatio.ALLOW_EXTRA,
)


type DanfossAirConfigEntry = ConfigEntry[DanfossAir]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import the Danfoss Air YAML configuration."""
    if DOMAIN in config:
        hass.async_create_task(_async_import(hass, config[DOMAIN]))
    return True


async def _async_import(hass: HomeAssistant, conf: ConfigType) -> None:
    """Import the YAML configuration into a config entry and raise an issue."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: conf[CONF_HOST]}
    )
    if (
        result["type"] is FlowResultType.ABORT
        and result["reason"] != "already_configured"
    ):
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version="2027.7.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )
        return

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.7.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_entry(hass: HomeAssistant, entry: DanfossAirConfigEntry) -> None:
    """Set up Danfoss Air from a config entry."""
    danfoss_air = DanfossAir(entry.data[CONF_HOST])
    await hass.async_add_executor_job(danfoss_air.update)
    if not danfoss_air.available:
        raise ConfigEntryNotReady(
            f"Cannot connect to the Danfoss Air CCM module at {entry.data[CONF_HOST]}"
        )

    entry.runtime_data = danfoss_air
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: DanfossAirConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


class DanfossAir:
    """Handle all communication with Danfoss Air CCM unit."""

    def __init__(self, host):
        """Initialize the Danfoss Air CCM connection."""
        self._data = {}
        self.available = True
        self._lock = threading.Lock()
        self._last_update: datetime | None = None

        self._client = DanfossClient(host)

    def get_value(self, item):
        """Get value for sensor."""
        return self._data.get(item)

    def update_state(self, command, state_command):
        """Send update command to Danfoss Air CCM."""
        with self._lock:
            self._data[state_command] = self._client.command(command)

    def update(self) -> None:
        """Fetch new data, at most once per MIN_TIME_BETWEEN_UPDATES.

        Every entity calls this from its own update, often at the same time.
        A caller that arrives while a fetch is running waits for it, instead
        of reading the data before it is filled in.
        """
        with self._lock:
            if (
                self._last_update is not None
                and dt_util.utcnow() - self._last_update < MIN_TIME_BETWEEN_UPDATES
            ):
                return
            self._update()
            self._last_update = dt_util.utcnow()

    def _update(self) -> None:
        """Use the data from Danfoss Air API."""
        _LOGGER.debug("Fetching data from Danfoss Air CCM module")

        try:
            self._fetch()
        except OSError as err:
            if self.available:
                _LOGGER.warning("Lost connection to Danfoss Air CCM module: %s", err)
            self.available = False
            return

        if not self.available:
            _LOGGER.info("Connection to Danfoss Air CCM module restored")
        self.available = True

        _LOGGER.debug("Done fetching data from Danfoss Air CCM module")

    def _fetch(self) -> None:
        """Read all values from the Danfoss Air CCM module."""
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
        self._data[ReadCommand.fan_speed_percent] = self._client.command(
            ReadCommand.fan_speed_percent
        )
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
