"""Support for switches which integrates with other components."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_NAME,
    CONF_STATE,
    CONF_SWITCHES,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TriggerUpdateCoordinator
from .const import CONF_TURN_OFF, CONF_TURN_ON
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA,
    make_template_entity_common_modern_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

_VALID_STATES = [STATE_ON, STATE_OFF, "true", "false"]

LEGACY_FIELDS = {
    CONF_VALUE_TEMPLATE: CONF_STATE,
}

DEFAULT_NAME = "Template Switch"

SWITCH_COMMON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_STATE): cv.template,
        vol.Optional(CONF_TURN_ON): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_TURN_OFF): cv.SCRIPT_SCHEMA,
    }
)

SWITCH_YAML_SCHEMA = SWITCH_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA
).extend(make_template_entity_common_modern_schema(SWITCH_DOMAIN, DEFAULT_NAME).schema)

SWITCH_LEGACY_YAML_SCHEMA = vol.All(
    cv.deprecated(ATTR_ENTITY_ID),
    vol.Schema(
        {
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
            vol.Required(CONF_TURN_ON): cv.SCRIPT_SCHEMA,
            vol.Required(CONF_TURN_OFF): cv.SCRIPT_SCHEMA,
            vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
            vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    ).extend(TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY.schema),
)

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SWITCHES): cv.schema_with_slug_keys(SWITCH_LEGACY_YAML_SCHEMA)}
)

SWITCH_CONFIG_ENTRY_SCHEMA = SWITCH_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template switches."""
    await async_setup_template_platform(
        hass,
        SWITCH_DOMAIN,
        config,
        StateSwitchEntity,
        TriggerSwitchEntity,
        async_add_entities,
        discovery_info,
        LEGACY_FIELDS,
        legacy_key=CONF_SWITCHES,
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
        StateSwitchEntity,
        SWITCH_CONFIG_ENTRY_SCHEMA,
        True,
    )


@callback
def async_create_preview_switch(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateSwitchEntity:
    """Create a preview switch."""
    return async_setup_template_preview(
        hass,
        name,
        config,
        StateSwitchEntity,
        SWITCH_CONFIG_ENTRY_SCHEMA,
        True,
    )


class AbstractTemplateSwitch(AbstractTemplateEntity, SwitchEntity, RestoreEntity):
    """Representation of a template switch features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(self, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Fire the on action."""
        if on_script := self._action_scripts.get(CONF_TURN_ON):
            await self.async_run_actions(on_script, context=self._context)
        if self._attr_assumed_state:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Fire the off action."""
        if off_script := self._action_scripts.get(CONF_TURN_OFF):
            await self.async_run_actions(off_script, context=self._context)
        if self._attr_assumed_state:
            self._attr_is_on = False
            self.async_write_ha_state()


class StateSwitchEntity(TemplateEntity, AbstractTemplateSwitch):
    """Representation of a Template switch."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Initialize the Template switch."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        AbstractTemplateSwitch.__init__(self, config)

        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        # Scripts can be an empty list, therefore we need to check for None
        if (on_action := config.get(CONF_TURN_ON)) is not None:
            self.add_actions(CONF_TURN_ON, on_action, name)
        if (off_action := config.get(CONF_TURN_OFF)) is not None:
            self.add_actions(CONF_TURN_OFF, off_action, name)

    @callback
    def _update_state(self, result):
        super()._update_state(result)
        if isinstance(result, TemplateError):
            self._attr_is_on = None
            return

        if isinstance(result, bool):
            self._attr_is_on = result
            return

        if isinstance(result, str):
            self._attr_is_on = result.lower() in ("true", STATE_ON)
            return

        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        if self._template is None:
            # restore state after startup
            await super().async_added_to_hass()
            if state := await self.async_get_last_state():
                self._attr_is_on = state.state == STATE_ON
        await super().async_added_to_hass()

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        if self._template is not None:
            self.add_template_attribute(
                "_attr_is_on", self._template, None, self._update_state
            )

        super()._async_setup_templates()


class TriggerSwitchEntity(TriggerEntity, AbstractTemplateSwitch):
    """Switch entity based on trigger data."""

    domain = SWITCH_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        AbstractTemplateSwitch.__init__(self, config)

        name = self._rendered.get(CONF_NAME, DEFAULT_NAME)
        if on_action := config.get(CONF_TURN_ON):
            self.add_actions(CONF_TURN_ON, on_action, name)
        if off_action := config.get(CONF_TURN_OFF):
            self.add_actions(CONF_TURN_OFF, off_action, name)

        if CONF_STATE in config:
            self._to_render_simple.append(CONF_STATE)
            self._parse_result.add(CONF_STATE)

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if (
            (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            # The trigger might have fired already while we waited for stored data,
            # then we should not restore state
            and self.is_on is None
        ):
            self._attr_is_on = last_state.state == STATE_ON
            self.restore_attributes(last_state)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update of the data."""
        self._process_data()

        if not self.available:
            self.async_write_ha_state()
            return

        write_ha_state = False
        if (state := self._rendered.get(CONF_STATE)) is not None:
            self._attr_is_on = template.result_as_boolean(state)
            write_ha_state = True

        elif len(self._rendered) > 0:
            # In case name, icon, or friendly name have a template but
            # states does not
            write_ha_state = True

        if write_ha_state:
            self.async_write_ha_state()
