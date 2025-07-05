"""Support for Template alarm control panels."""

from __future__ import annotations

from collections.abc import Generator, Sequence
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
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, selector, template
from homeassistant.helpers.device import async_device_info_to_link_from_device_id
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_OBJECT_ID, DOMAIN
from .coordinator import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity
from .template_entity import (
    LEGACY_FIELDS as TEMPLATE_ENTITY_LEGACY_FIELDS,
    TemplateEntity,
    make_template_entity_common_modern_schema,
    rewrite_common_legacy_to_modern_conf,
)
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [
    AlarmControlPanelState.ARMED_AWAY,
    AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
    AlarmControlPanelState.ARMED_HOME,
    AlarmControlPanelState.ARMED_NIGHT,
    AlarmControlPanelState.ARMED_VACATION,
    AlarmControlPanelState.ARMING,
    AlarmControlPanelState.DISARMED,
    AlarmControlPanelState.DISARMING,
    AlarmControlPanelState.PENDING,
    AlarmControlPanelState.TRIGGERED,
    STATE_UNAVAILABLE,
]

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


LEGACY_FIELDS = TEMPLATE_ENTITY_LEGACY_FIELDS | {
    CONF_VALUE_TEMPLATE: CONF_STATE,
}

DEFAULT_NAME = "Template Alarm Control Panel"

ALARM_CONTROL_PANEL_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_ARM_AWAY_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_ARM_CUSTOM_BYPASS_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_ARM_HOME_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_ARM_NIGHT_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_ARM_VACATION_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_CODE_ARM_REQUIRED, default=True): cv.boolean,
            vol.Optional(
                CONF_CODE_FORMAT, default=TemplateCodeFormat.number.name
            ): cv.enum(TemplateCodeFormat),
            vol.Optional(CONF_DISARM_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_STATE): cv.template,
            vol.Optional(CONF_TRIGGER_ACTION): cv.SCRIPT_SCHEMA,
        }
    ).extend(make_template_entity_common_modern_schema(DEFAULT_NAME).schema)
)


LEGACY_ALARM_CONTROL_PANEL_SCHEMA = vol.Schema(
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
            LEGACY_ALARM_CONTROL_PANEL_SCHEMA
        ),
    }
)

ALARM_CONTROL_PANEL_CONFIG_SCHEMA = vol.Schema(
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
        vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
        vol.Optional(CONF_DISARM_ACTION): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_NAME): cv.template,
        vol.Optional(CONF_STATE): cv.template,
        vol.Optional(CONF_TRIGGER_ACTION): cv.SCRIPT_SCHEMA,
    }
)


def rewrite_legacy_to_modern_conf(
    hass: HomeAssistant, config: dict[str, dict]
) -> list[dict]:
    """Rewrite legacy alarm control panel configuration definitions to modern ones."""
    alarm_control_panels = []

    for object_id, entity_conf in config.items():
        entity_conf = {**entity_conf, CONF_OBJECT_ID: object_id}

        entity_conf = rewrite_common_legacy_to_modern_conf(
            hass, entity_conf, LEGACY_FIELDS
        )

        if CONF_NAME not in entity_conf:
            entity_conf[CONF_NAME] = template.Template(object_id, hass)

        alarm_control_panels.append(entity_conf)

    return alarm_control_panels


@callback
def _async_create_template_tracking_entities(
    async_add_entities: AddEntitiesCallback,
    hass: HomeAssistant,
    definitions: list[dict],
    unique_id_prefix: str | None,
) -> None:
    """Create the template alarm control panels."""
    alarm_control_panels = []

    for entity_conf in definitions:
        unique_id = entity_conf.get(CONF_UNIQUE_ID)

        if unique_id and unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"

        alarm_control_panels.append(
            AlarmControlPanelTemplate(
                hass,
                entity_conf,
                unique_id,
            )
        )

    async_add_entities(alarm_control_panels)


def rewrite_options_to_modern_conf(option_config: dict[str, dict]) -> dict[str, dict]:
    """Rewrite option configuration to modern configuration."""
    option_config = {**option_config}

    if CONF_VALUE_TEMPLATE in option_config:
        option_config[CONF_STATE] = option_config.pop(CONF_VALUE_TEMPLATE)

    return option_config


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    _options = dict(config_entry.options)
    _options.pop("template_type")
    _options = rewrite_options_to_modern_conf(_options)
    validated_config = ALARM_CONTROL_PANEL_CONFIG_SCHEMA(_options)
    async_add_entities(
        [
            AlarmControlPanelTemplate(
                hass,
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
    """Set up the Template cover."""
    if discovery_info is None:
        _async_create_template_tracking_entities(
            async_add_entities,
            hass,
            rewrite_legacy_to_modern_conf(hass, config[CONF_ALARM_CONTROL_PANELS]),
            None,
        )
        return

    if "coordinator" in discovery_info:
        async_add_entities(
            TriggerAlarmControlPanelEntity(hass, discovery_info["coordinator"], config)
            for config in discovery_info["entities"]
        )
        return

    _async_create_template_tracking_entities(
        async_add_entities,
        hass,
        discovery_info["entities"],
        discovery_info["unique_id"],
    )


class AbstractTemplateAlarmControlPanel(
    AbstractTemplateEntity, AlarmControlPanelEntity, RestoreEntity
):
    """Representation of a templated Alarm Control Panel features."""

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(self, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""
        self._template = config.get(CONF_STATE)

        self._attr_code_arm_required: bool = config[CONF_CODE_ARM_REQUIRED]
        self._attr_code_format = config[CONF_CODE_FORMAT].value

        self._state: AlarmControlPanelState | None = None
        self._attr_supported_features: AlarmControlPanelEntityFeature = (
            AlarmControlPanelEntityFeature(0)
        )

    def _iterate_scripts(
        self, config: dict[str, Any]
    ) -> Generator[
        tuple[str, Sequence[dict[str, Any]], AlarmControlPanelEntityFeature | int]
    ]:
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
            if (action_config := config.get(action_id)) is not None:
                yield (action_id, action_config, supported_feature)

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the device."""
        return self._state

    async def _async_handle_restored_state(self) -> None:
        if (
            (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            and last_state.state in _VALID_STATES
            # The trigger might have fired already while we waited for stored data,
            # then we should not restore state
            and self._state is None
        ):
            self._state = AlarmControlPanelState(last_state.state)

    def _handle_state(self, result: Any) -> None:
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

    async def _async_alarm_arm(self, state: Any, script: Script | None, code: Any):
        """Arm the panel to specified state with supplied script."""
        optimistic_set = False

        if self._template is None:
            self._state = state
            optimistic_set = True

        if script:
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


class AlarmControlPanelTemplate(TemplateEntity, AbstractTemplateAlarmControlPanel):
    """Representation of a templated Alarm Control Panel."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
        unique_id: str | None,
    ) -> None:
        """Initialize the panel."""
        TemplateEntity.__init__(self, hass, config=config, unique_id=unique_id)
        AbstractTemplateAlarmControlPanel.__init__(self, config)
        if (object_id := config.get(CONF_OBJECT_ID)) is not None:
            self.entity_id = async_generate_entity_id(
                ENTITY_ID_FORMAT, object_id, hass=hass
            )
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        for action_id, action_config, supported_feature in self._iterate_scripts(
            config
        ):
            self.add_script(action_id, action_config, name, DOMAIN)
            self._attr_supported_features |= supported_feature

        self._attr_device_info = async_device_info_to_link_from_device_id(
            hass,
            config.get(CONF_DEVICE_ID),
        )

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        await self._async_handle_restored_state()

    @callback
    def _update_state(self, result):
        if isinstance(result, TemplateError):
            self._state = None
            return

        self._handle_state(result)

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        if self._template:
            self.add_template_attribute(
                "_state", self._template, None, self._update_state
            )
        super()._async_setup_templates()


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
        AbstractTemplateAlarmControlPanel.__init__(self, config)

        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)

        if isinstance(config.get(CONF_STATE), template.Template):
            self._to_render_simple.append(CONF_STATE)
            self._parse_result.add(CONF_STATE)

        for action_id, action_config, supported_feature in self._iterate_scripts(
            config
        ):
            self.add_script(action_id, action_config, name, DOMAIN)
            self._attr_supported_features |= supported_feature

        self._attr_device_info = async_device_info_to_link_from_device_id(
            hass,
            config.get(CONF_DEVICE_ID),
        )

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

        if (rendered := self._rendered.get(CONF_STATE)) is not None:
            self._handle_state(rendered)
            self.async_set_context(self.coordinator.data["context"])
            self.async_write_ha_state()
