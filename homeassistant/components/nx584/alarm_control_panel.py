"""Support for NX584 alarm control panels."""

from datetime import timedelta
import logging
from typing import override

from nx584 import client
import requests
import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    PLATFORM_SCHEMA as ALARM_CONTROL_PANEL_PLATFORM_SCHEMA,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import NX584ConfigEntry, async_import_yaml_config
from .const import DEFAULT_HOST, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

DEFAULT_NAME = "NX584"
SERVICE_BYPASS_ZONE = "bypass_zone"
SERVICE_UNBYPASS_ZONE = "unbypass_zone"
ATTR_ZONE = "zone"

PLATFORM_SCHEMA = ALARM_CONTROL_PANEL_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


def _async_register_services() -> None:
    """Register the bypass/unbypass zone entity services."""
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_BYPASS_ZONE,
        {vol.Required(ATTR_ZONE): cv.positive_int},
        "alarm_bypass",
    )

    platform.async_register_entity_service(
        SERVICE_UNBYPASS_ZONE,
        {vol.Required(ATTR_ZONE): cv.positive_int},
        "alarm_unbypass",
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the NX584 platform from YAML, importing it as a config entry."""
    await async_import_yaml_config(hass, config)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NX584ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the NX584 alarm control panel from a config entry."""
    data = entry.runtime_data

    # NX584Alarm has no unique_id, so its entity_id is derived from this name.
    # Use the same stable default YAML used rather than entry.title (the host),
    # so entity_id doesn't change for existing users migrating from YAML.
    entity = NX584Alarm(DEFAULT_NAME, data.client)
    async_add_entities([entity])

    _async_register_services()


class NX584Alarm(AlarmControlPanelEntity):
    """Representation of a NX584-based alarm panel."""

    _attr_code_format = CodeFormat.NUMBER
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )
    _attr_code_arm_required = False

    def __init__(self, name: str, alarm_client: client.Client) -> None:
        """Init the nx584 alarm panel."""
        self._attr_name = name
        self._alarm = alarm_client

    def update(self) -> None:
        """Process new events from panel."""
        try:
            part = self._alarm.list_partitions()[0]
            zones = self._alarm.list_zones()
        except requests.exceptions.ConnectionError as ex:
            _LOGGER.error(
                "Unable to connect to %(name)s: %(reason)s",
                {"name": self._attr_name, "reason": ex},
            )
            self._attr_available = False
            return
        except IndexError:
            _LOGGER.error("NX584 reports no partitions")
            self._attr_available = False
            return

        self._attr_available = True
        bypassed = False
        for zone in zones:
            if zone["bypassed"]:
                _LOGGER.debug(
                    "Zone %(zone)s is bypassed, assuming HOME",
                    {"zone": zone["number"]},
                )
                bypassed = True
                break

        if not part["armed"]:
            self._attr_alarm_state = AlarmControlPanelState.DISARMED
        elif bypassed:
            self._attr_alarm_state = AlarmControlPanelState.ARMED_HOME
        else:
            self._attr_alarm_state = AlarmControlPanelState.ARMED_AWAY

        for flag in part["condition_flags"]:
            if flag == "Siren on":
                self._attr_alarm_state = AlarmControlPanelState.TRIGGERED

    @override
    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        self._alarm.disarm(code)

    @override
    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        self._alarm.arm("stay")

    @override
    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        self._alarm.arm("exit")

    def alarm_bypass(self, zone: int) -> None:
        """Send bypass command."""
        self._alarm.set_bypass(zone, True)

    def alarm_unbypass(self, zone: int) -> None:
        """Send bypass command."""
        self._alarm.set_bypass(zone, False)
