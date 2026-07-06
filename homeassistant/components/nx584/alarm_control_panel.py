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
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_validation as cv,
    entity_platform,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import NX584ConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "NX584"
DEFAULT_PORT = 5007
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
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "NX584",
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "NX584",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NX584ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the NX584 alarm control panel from a config entry."""
    data = entry.runtime_data

    entity = NX584Alarm(data.client, data.url, entry.entry_id)
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
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, alarm_client: client.Client, url: str, entry_id: str) -> None:
        """Init the nx584 alarm panel."""
        self._alarm = alarm_client
        self._url = url
        self._attr_unique_id = entry_id
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry_id)})

    def update(self) -> None:
        """Process new events from panel."""
        try:
            part = self._alarm.list_partitions()[0]
            zones = self._alarm.list_zones()
        except requests.exceptions.ConnectionError as ex:
            _LOGGER.error(
                "Unable to connect to %(host)s: %(reason)s",
                {"host": self._url, "reason": ex},
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
