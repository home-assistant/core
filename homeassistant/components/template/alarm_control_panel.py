"""Support for Template alarm control panels."""

from __future__ import annotations

from enum import Enum
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
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
    CONF_NAME,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import validators as tcv
from .const import DOMAIN
from .coordinator import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA,
    make_template_entity_common_modern_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

CONF_ALARM_CONTROL_PANELS = "panels"
CONF_ARM_AWAY_ACTION = "arm_away"
CONF_ARM_CUSTOM_BYPASS_ACTION = "arm_custom_bypass"
CONF_ARM_HOME_ACTION = "arm_home"
CONF_ARM_NIGHT_ACTION = "arm_night"
CONF_ARM_VACATION_ACTION = "arm_vacation"
CONF_CODE_ARM_REQUIRED = "code_arm_required"
CONF_CODE_FORMAT = "code_format"
CONF_DISARM_ACTION = "disarm"
CONF_TRIGGER_ACTION = "trigger"


class TemplateCodeFormat(Enum):
    """Class to represent different code formats."""

    no_code = None
    number = CodeFormat.NUMBER
    text = CodeFormat.TEXT


LEGACY_FIELDS = {
    CONF_VALUE_TEMPLATE: CONF_STATE,
}

DEFAULT_NAME = "Template Alarm Control Panel"

ALARM_CONTROL_PANEL_COMMON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ARM_AWAY_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_CUSTOM_BYPASS_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_HOME_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_NIGHT_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_VACATION_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_CODE_ARM_REQUIRED, default=True): cv.boolean,
        vol.Optional(CONF_CODE_FORMAT, default=TemplateCodeFormat.number.name): cv.enum(
            TemplateCodeFormat
        ),
        vol.Optional(CONF_DISARM_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_STATE): cv.template,
        vol.Optional(CONF_TRIGGER_ACTION): cv.SCRIPT_SCHEMA,
    }
)

ALARM_CONTROL_PANEL_YAML_SCHEMA = ALARM_CONTROL_PANEL_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA
).extend(
    make_template_entity_common_modern_schema(
        ALARM_CONTROL_PANEL_DOMAIN, DEFAULT_NAME
    ).schema
)

ALARM_CONTROL_PANEL_LEGACY_YAML_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ARM_AWAY_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_CUSTOM_BYPASS_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_HOME_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_NIGHT_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_VACATION_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_CODE_ARM_REQUIRED, default=True): cv.boolean,
        vol.Optional(CONF_CODE_FORMAT, default=TemplateCodeFormat.number.name): cv.enum(
            TemplateCodeFormat
        ),
        vol.Optional(CONF_DISARM_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_TRIGGER_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
)

PLATFORM_SCHEMA = ALARM_CONTROL_PANEL_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ALARM_CONTROL_PANELS): cv.schema_with_slug_keys(
            ALARM_CONTROL_PANEL_LEGACY_YAML_SCHEMA
        ),
    }
)

ALARM_CONTROL_PANEL_CONFIG_ENTRY_SCHEMA = ALARM_CONTROL_PANEL_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    await async_setup_template_entry(
        hass,
        config_entry,
        async_add_entities,
        StateAlarmControlPanelEntity,
        ALARM_CONTROL_PANEL_CONFIG_ENTRY_SCHEMA,
        True,
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Template cover."""
    await async_setup_template_platform(
        hass,
        ALARM_CONTROL_PANEL_DOMAIN,
        config,
        StateAlarmControlPanelEntity,
        TriggerAlarmControlPanelEntity,
        async_add_entities,
        discovery_info,
        LEGACY_FIELDS,
        legacy_key=CONF_ALARM_CONTROL_PANELS,
    )


@callback
def async_create_preview_alarm_control_panel(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateAlarmControlPanelEntity:
    """Create a preview alarm control panel."""
    return async_setup_template_preview(
        hass,
        name,
        config,
        StateAlarmControlPanelEntity,
        ALARM_CONTROL_PANEL_CONFIG_ENTRY_SCHEMA,
        True,
    )


class AbstractTemplateAlarmControlPanel(
    AbstractTemplateEntity, AlarmControlPanelEntity, RestoreEntity
):
    """Representation of a templated Alarm Control Panel features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True

    # The super init is not called because TemplateEntity calls AbstractTemplateEntity.__init__.
    def __init__(self, name: str) -> None:  # pylint: disable=super-init-not-called
        """Setup the templates and scripts."""

        self._attr_code_arm_required: bool = self._config[CONF_CODE_ARM_REQUIRED]
        self._attr_code_format = self._config[CONF_CODE_FORMAT].value

        self.setup_state_template(
            CONF_STATE,
            "_attr_alarm_state",
            validator=tcv.strenum(self, CONF_STATE, AlarmControlPanelState),
        )

        self._attr_supported_features: AlarmControlPanelEntityFeature = (
            AlarmControlPanelEntityFeature(0)
        )
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
            if (action_config := self._config.get(action_id)) is not None:
                self.add_script(action_id, action_config, name, DOMAIN)
                self._attr_supported_features |= supported_feature

    async def _async_handle_restored_state(self) -> None:
        if (
            (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            and last_state.state in AlarmControlPanelState
            # The trigger might have fired already while we waited for stored data,
            # then we should not restore state
            and self._attr_alarm_state is None
        ):
            self._attr_alarm_state = AlarmControlPanelState(last_state.state)

    async def _async_alarm_arm(self, state: Any, script: Script | None, code: Any):
        """Arm the panel to specified state with supplied script."""

        if script:
            await self.async_run_script(
                script, run_variables={ATTR_CODE: code}, context=self._context
            )

        if self._attr_assumed_state:
            self._attr_alarm_state = state
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


class StateAlarmControlPanelEntity(TemplateEntity, AbstractTemplateAlarmControlPanel):
    """Representation of a templated Alarm Control Panel."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
        unique_id: str | None,
    ) -> None:
        """Initialize the panel."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        AbstractTemplateAlarmControlPanel.__init__(self, name)

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        await self._async_handle_restored_state()


class TriggerAlarmControlPanelEntity(TriggerEntity, AbstractTemplateAlarmControlPanel):
    """Alarm Control Panel entity based on trigger data."""

    domain = ALARM_CONTROL_PANEL_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)
        AbstractTemplateAlarmControlPanel.__init__(self, name)

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        await self._async_handle_restored_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update of the data."""
        self._process_data()

        if not self.available:
            self.async_write_ha_state()
            return

        if self.handle_rendered_result(CONF_STATE):
            self.async_set_context(self.coordinator.data["context"])
            self.async_write_ha_state()
