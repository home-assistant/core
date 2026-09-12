"""Support for Concord232 alarm control panels."""

import datetime
import logging
from typing import override

from concord232 import client as concord232_client
import requests
import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    PLATFORM_SCHEMA as ALARM_CONTROL_PANEL_PLATFORM_SCHEMA,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CODE,
    CONF_HOST,
    CONF_MODE,
    CONF_NAME,
    CONF_PORT,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import async_import_yaml, build_url
from .const import DEFAULT_MODE, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "CONCORD232"

SCAN_INTERVAL = datetime.timedelta(seconds=10)

PLATFORM_SCHEMA = ALARM_CONTROL_PANEL_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_CODE): cv.string,
        vol.Optional(CONF_MODE, default=DEFAULT_MODE): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the YAML platform configuration and create a config entry."""
    await async_import_yaml(hass, config, Platform.ALARM_CONTROL_PANEL)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Concord232 alarm control panel from a config entry."""
    url = build_url(entry.data[CONF_HOST], entry.data[CONF_PORT])
    # "" is the options flow's explicit cleared-code marker
    code: str | None = entry.options.get(CONF_CODE) or None
    mode: str = entry.options.get(CONF_MODE, DEFAULT_MODE)
    try:
        # The constructor does blocking I/O against the server
        alarm = await hass.async_add_executor_job(
            Concord232Alarm, url, entry.title, code, mode
        )
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error("Unable to connect to Concord232: %s", str(ex))
        return
    async_add_entities([alarm], True)


class Concord232Alarm(AlarmControlPanelEntity):
    """Representation of the Concord232-based alarm panel."""

    _attr_code_format = CodeFormat.NUMBER
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )

    def __init__(self, url: str, name: str, code: str | None, mode: str) -> None:
        """Initialize the Concord232 alarm panel."""

        self._attr_name = name
        self._code = code
        self._alarm_control_panel_option_default_code = code
        # The panel protocol arms without a code; only require one when the
        # user configured a code to gate arming locally.
        self._attr_code_arm_required = code is not None
        self._mode = mode
        self._url = url
        self._alarm = concord232_client.Client(self._url)
        self._alarm.partitions = self._alarm.list_partitions()

    def update(self) -> None:
        """Update values from API."""
        try:
            part = self._alarm.list_partitions()[0]
        except requests.exceptions.ConnectionError as ex:
            _LOGGER.error(
                "Unable to connect to %(host)s: %(reason)s",
                {"host": self._url, "reason": ex},
            )
            return
        except IndexError:
            _LOGGER.error("Concord232 reports no partitions")
            return

        if part["arming_level"] == "Off":
            self._attr_alarm_state = AlarmControlPanelState.DISARMED
        elif "Home" in part["arming_level"]:
            self._attr_alarm_state = AlarmControlPanelState.ARMED_HOME
        else:
            self._attr_alarm_state = AlarmControlPanelState.ARMED_AWAY

    @override
    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if not self._validate_code(code, AlarmControlPanelState.DISARMED):
            return
        self._alarm.disarm(code)

    @override
    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        if not self._validate_code(code, AlarmControlPanelState.ARMED_HOME):
            return
        if self._mode == "silent":
            self._alarm.arm("stay", "silent")
        else:
            self._alarm.arm("stay")

    @override
    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if not self._validate_code(code, AlarmControlPanelState.ARMED_AWAY):
            return
        self._alarm.arm("away")

    def _validate_code(self, code: str | None, state: AlarmControlPanelState) -> bool:
        """Validate given code."""
        if self._code is None:
            return True
        alarm_code = self._code
        check = not alarm_code or code == alarm_code
        if not check:
            _LOGGER.warning("Invalid code given for %s", state)
        return check
