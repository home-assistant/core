"""Support for Concord232 alarm control panels."""

import logging
from typing import override

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    PLATFORM_SCHEMA as ALARM_CONTROL_PANEL_PLATFORM_SCHEMA,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_MODE, CONF_NAME, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_MODE, DEFAULT_PORT, DOMAIN, MODE_SILENT
from .coordinator import Concord232ConfigEntry, Concord232Coordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "CONCORD232"

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
    await _async_import_yaml(hass, config)


async def _async_import_yaml(hass: HomeAssistant, config: ConfigType) -> None:
    """Start an import flow and create the deprecation repair issue."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=dict(config)
    )
    if result["type"] is FlowResultType.ABORT and result["reason"] == "cannot_connect":
        ir.async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_import_issue_cannot_connect",
            breaks_in_ha_version="2027.3.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue_cannot_connect",
        )
        return
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.3.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Concord232",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Concord232ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Concord232 alarm control panel from a config entry."""
    async_add_entities([Concord232Alarm(entry)])


class Concord232Alarm(
    CoordinatorEntity[Concord232Coordinator], AlarmControlPanelEntity
):
    """Representation of the Concord232-based alarm panel."""

    _attr_code_format = CodeFormat.NUMBER
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )

    def __init__(self, entry: Concord232ConfigEntry) -> None:
        """Initialize the Concord232 alarm panel."""
        super().__init__(entry.runtime_data)
        self._attr_unique_id = f"{entry.entry_id}_panel"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GE Interlogix",
            model="Concord",
        )
        code: str | None = entry.options.get(CONF_CODE)
        self._code = code
        self._alarm_control_panel_option_default_code = code
        # The panel protocol arms without a code; only require one when the
        # user configured a code to gate arming locally.
        self._attr_code_arm_required = code is not None
        self._mode: str = entry.options.get(CONF_MODE, DEFAULT_MODE)

    @property
    @override
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the panel."""
        partitions = self.coordinator.data.partitions
        if not partitions:
            return None
        arming_level: str = partitions[0]["arming_level"]
        if arming_level == "Off":
            return AlarmControlPanelState.DISARMED
        if "Home" in arming_level:
            return AlarmControlPanelState.ARMED_HOME
        return AlarmControlPanelState.ARMED_AWAY

    @override
    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if not self._validate_code(code, AlarmControlPanelState.DISARMED):
            return
        await self.hass.async_add_executor_job(self.coordinator.client.disarm, code)
        await self.coordinator.async_request_refresh()

    @override
    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        if not self._validate_code(code, AlarmControlPanelState.ARMED_HOME):
            return
        if self._mode == MODE_SILENT:
            await self.hass.async_add_executor_job(
                self.coordinator.client.arm, "stay", "silent"
            )
        else:
            await self.hass.async_add_executor_job(self.coordinator.client.arm, "stay")
        await self.coordinator.async_request_refresh()

    @override
    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if not self._validate_code(code, AlarmControlPanelState.ARMED_AWAY):
            return
        await self.hass.async_add_executor_job(self.coordinator.client.arm, "away")
        await self.coordinator.async_request_refresh()

    def _validate_code(self, code: str | None, state: AlarmControlPanelState) -> bool:
        """Validate given code."""
        if self._code is None:
            return True
        check = code == self._code
        if not check:
            _LOGGER.warning("Invalid code given for %s", state)
        return check
