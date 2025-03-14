"""Support for Template alarm control panels."""

from __future__ import annotations

from enum import Enum
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as ALARM_CONTROL_PANEL_PLATFORM_SCHEMA,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CODE,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.device import async_device_info_to_link_from_device_id
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from .const import DOMAIN
from .template_entity import TemplateEntity, rewrite_common_legacy_to_modern_conf

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [
    AlarmControlPanelState.ARMED_AWAY,
    AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
    AlarmControlPanelState.ARMED_HOME,
    AlarmControlPanelState.ARMED_NIGHT,
    AlarmControlPanelState.ARMED_VACATION,
    AlarmControlPanelState.ARMING,
    AlarmControlPanelState.DISARMED,
    AlarmControlPanelState.PENDING,
    AlarmControlPanelState.TRIGGERED,
    STATE_UNAVAILABLE,
]

CONF_ARM_AWAY_ACTION = "arm_away"
CONF_ARM_CUSTOM_BYPASS_ACTION = "arm_custom_bypass"
CONF_ARM_HOME_ACTION = "arm_home"
CONF_ARM_NIGHT_ACTION = "arm_night"
CONF_ARM_VACATION_ACTION = "arm_vacation"
CONF_DISARM_ACTION = "disarm"
CONF_TRIGGER_ACTION = "trigger"
CONF_ALARM_CONTROL_PANELS = "panels"
CONF_CODE_ARM_REQUIRED = "code_arm_required"
CONF_CODE_FORMAT = "code_format"


class TemplateCodeFormat(Enum):
    """Class to represent different code formats."""

    no_code = None
    number = CodeFormat.NUMBER
    text = CodeFormat.TEXT


ALARM_CONTROL_PANEL_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_DISARM_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_AWAY_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_CUSTOM_BYPASS_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_HOME_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_NIGHT_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_VACATION_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_TRIGGER_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_CODE_ARM_REQUIRED, default=True): cv.boolean,
        vol.Optional(CONF_CODE_FORMAT, default=TemplateCodeFormat.number.name): cv.enum(
            TemplateCodeFormat
        ),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

PLATFORM_SCHEMA = ALARM_CONTROL_PANEL_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ALARM_CONTROL_PANELS): cv.schema_with_slug_keys(
            ALARM_CONTROL_PANEL_SCHEMA
        ),
    }
)

ALARM_CONTROL_PANEL_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.template,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_DISARM_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_AWAY_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_CUSTOM_BYPASS_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_HOME_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_NIGHT_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_VACATION_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_TRIGGER_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_CODE_ARM_REQUIRED, default=True): cv.boolean,
        vol.Optional(CONF_CODE_FORMAT, default=TemplateCodeFormat.number.name): cv.enum(
            TemplateCodeFormat
        ),
        vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
    }
)


async def _async_create_entities(
    hass: HomeAssistant, config: dict[str, Any]
) -> list[AlarmControlPanelTemplate]:
    """Create Template Alarm Control Panels."""
    alarm_control_panels = []

    for object_id, entity_config in config[CONF_ALARM_CONTROL_PANELS].items():
        entity_config = rewrite_common_legacy_to_modern_conf(hass, entity_config)
        unique_id = entity_config.get(CONF_UNIQUE_ID)

        alarm_control_panels.append(
            AlarmControlPanelTemplate(
                hass,
                object_id,
                entity_config,
                unique_id,
            )
        )

    return alarm_control_panels


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    _options = dict(config_entry.options)
    _options.pop("template_type")
    validated_config = ALARM_CONTROL_PANEL_CONFIG_SCHEMA(_options)
    async_add_entities(
        [
            AlarmControlPanelTemplate(
                hass,
                slugify(_options[CONF_NAME]),
                validated_config,
                config_entry.entry_id,
            )
        ]
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Template Alarm Control Panels."""
    async_add_entities(await _async_create_entities(hass, config))


class AlarmControlPanelTemplate(TemplateEntity, AlarmControlPanelEntity, RestoreEntity):
    """Representation of a templated Alarm Control Panel."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        object_id: str,
        config: dict,
        unique_id: str | None,
    ) -> None:
        """Initialize the panel."""
        super().__init__(
            hass, config=config, fallback_name=object_id, unique_id=unique_id
        )
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, object_id, hass=hass
        )
        name = self._attr_name
        assert name is not None
        self._template = config.get(CONF_VALUE_TEMPLATE)
        self._attr_code_arm_required: bool = config[CONF_CODE_ARM_REQUIRED]
        self._attr_code_format = config[CONF_CODE_FORMAT].value

        self._attr_supported_features = AlarmControlPanelEntityFeature(0)
        for action_id, supported_feature in (
            (CONF_DISARM_ACTION, 0),
            (CONF_ARM_AWAY_ACTION, AlarmControlPanelEntityFeature.ARM_AWAY),
            (CONF_ARM_HOME_ACTION, AlarmControlPanelEntityFeature.ARM_HOME),
            (CONF_ARM_NIGHT_ACTION, AlarmControlPanelEntityFeature.ARM_NIGHT),
            (CONF_ARM_VACATION_ACTION, AlarmControlPanelEntityFeature.ARM_VACATION),
            (
                CONF_ARM_CUSTOM_BYPASS_ACTION,
                AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS,
            ),
            (CONF_TRIGGER_ACTION, AlarmControlPanelEntityFeature.TRIGGER),
        ):
            if action_config := config.get(action_id):
                self.add_script(action_id, action_config, name, DOMAIN)
                self._attr_supported_features |= supported_feature

        self._state: AlarmControlPanelState | None = None
        self._attr_device_info = async_device_info_to_link_from_device_id(
            hass,
            config.get(CONF_DEVICE_ID),
        )

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if (
            (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            and last_state.state in _VALID_STATES
            # The trigger might have fired already while we waited for stored data,
            # then we should not restore state
            and self._state is None
        ):
            self._state = AlarmControlPanelState(last_state.state)

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the device."""
        return self._state

    @callback
    def _update_state(self, result):
        if isinstance(result, TemplateError):
            self._state = None
            return

        # Validate state
        if result in _VALID_STATES:
            self._state = result
            _LOGGER.debug("Valid state - %s", result)
            return

        _LOGGER.error(
            "Received invalid alarm panel state: %s for entity %s. Expected: %s",
            result,
            self.entity_id,
            ", ".join(_VALID_STATES),
        )
        self._state = None

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        if self._template:
            self.add_template_attribute(
                "_state", self._template, None, self._update_state
            )
        super()._async_setup_templates()

    async def _async_alarm_arm(self, state, script, code):
        """Arm the panel to specified state with supplied script."""
        optimistic_set = False

        if self._template is None:
            self._state = state
            optimistic_set = True

        await self.async_run_script(
            script, run_variables={ATTR_CODE: code}, context=self._context
        )

        if optimistic_set:
            self.async_write_ha_state()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm the panel to Away."""
        await self._async_alarm_arm(
            AlarmControlPanelState.ARMED_AWAY,
            script=self._action_scripts.get(CONF_ARM_AWAY_ACTION),
            code=code,
        )

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm the panel to Home."""
        await self._async_alarm_arm(
            AlarmControlPanelState.ARMED_HOME,
            script=self._action_scripts.get(CONF_ARM_HOME_ACTION),
            code=code,
        )

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Arm the panel to Night."""
        await self._async_alarm_arm(
            AlarmControlPanelState.ARMED_NIGHT,
            script=self._action_scripts.get(CONF_ARM_NIGHT_ACTION),
            code=code,
        )

    async def async_alarm_arm_vacation(self, code: str | None = None) -> None:
        """Arm the panel to Vacation."""
        await self._async_alarm_arm(
            AlarmControlPanelState.ARMED_VACATION,
            script=self._action_scripts.get(CONF_ARM_VACATION_ACTION),
            code=code,
        )

    async def async_alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Arm the panel to Custom Bypass."""
        await self._async_alarm_arm(
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
            script=self._action_scripts.get(CONF_ARM_CUSTOM_BYPASS_ACTION),
            code=code,
        )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm the panel."""
        await self._async_alarm_arm(
            AlarmControlPanelState.DISARMED,
            script=self._action_scripts.get(CONF_DISARM_ACTION),
            code=code,
        )

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Trigger the panel."""
        await self._async_alarm_arm(
            AlarmControlPanelState.TRIGGERED,
            script=self._action_scripts.get(CONF_TRIGGER_ACTION),
            code=code,
        )
