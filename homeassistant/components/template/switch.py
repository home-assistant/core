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
    CONF_DEVICE_ID,
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
from homeassistant.helpers import config_validation as cv, selector, template
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TriggerUpdateCoordinator
from .const import CONF_TURN_OFF, CONF_TURN_ON, DOMAIN
from .helpers import async_setup_template_platform
from .template_entity import (
    TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY,
    TemplateEntity,
    make_template_entity_common_modern_schema,
)
from .trigger_entity import TriggerEntity

_VALID_STATES = [STATE_ON, STATE_OFF, "true", "false"]

LEGACY_FIELDS = {
    CONF_VALUE_TEMPLATE: CONF_STATE,
}

DEFAULT_NAME = "Template Switch"


SWITCH_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_STATE): cv.template,
        vol.Required(CONF_TURN_ON): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_TURN_OFF): cv.SCRIPT_SCHEMA,
    }
).extend(make_template_entity_common_modern_schema(DEFAULT_NAME).schema)

LEGACY_SWITCH_SCHEMA = vol.All(
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
    {vol.Required(CONF_SWITCHES): cv.schema_with_slug_keys(LEGACY_SWITCH_SCHEMA)}
)

SWITCH_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.template,
        vol.Optional(CONF_STATE): cv.template,
        vol.Optional(CONF_TURN_ON): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_TURN_OFF): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
    }
)


def rewrite_options_to_modern_conf(option_config: dict[str, dict]) -> dict[str, dict]:
    """Rewrite option configuration to modern configuration."""
    option_config = {**option_config}

    if CONF_VALUE_TEMPLATE in option_config:
        option_config[CONF_STATE] = option_config.pop(CONF_VALUE_TEMPLATE)

    return option_config


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
    _options = dict(config_entry.options)
    _options.pop("template_type")
    _options = rewrite_options_to_modern_conf(_options)
    validated_config = SWITCH_CONFIG_SCHEMA(_options)
    async_add_entities(
        [StateSwitchEntity(hass, validated_config, config_entry.entry_id)]
    )


@callback
def async_create_preview_switch(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateSwitchEntity:
    """Create a preview switch."""
    updated_config = rewrite_options_to_modern_conf(config)
    validated_config = SWITCH_CONFIG_SCHEMA(updated_config | {CONF_NAME: name})
    return StateSwitchEntity(hass, validated_config, None)


class StateSwitchEntity(TemplateEntity, SwitchEntity, RestoreEntity):
    """Representation of a Template switch."""

    _attr_should_poll = False
    _entity_id_format = ENTITY_ID_FORMAT

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Initialize the Template switch."""
        super().__init__(hass, config, unique_id)

        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None
        self._template = config.get(CONF_STATE)

        # Scripts can be an empty list, therefore we need to check for None
        if (on_action := config.get(CONF_TURN_ON)) is not None:
            self.add_script(CONF_TURN_ON, on_action, name, DOMAIN)
        if (off_action := config.get(CONF_TURN_OFF)) is not None:
            self.add_script(CONF_TURN_OFF, off_action, name, DOMAIN)

        self._state: bool | None = False
        self._attr_assumed_state = self._template is None

    @callback
    def _update_state(self, result):
        super()._update_state(result)
        if isinstance(result, TemplateError):
            self._state = None
            return

        if isinstance(result, bool):
            self._state = result
            return

        if isinstance(result, str):
            self._state = result.lower() in ("true", STATE_ON)
            return

        self._state = False

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        if self._template is None:
            # restore state after startup
            await super().async_added_to_hass()
            if state := await self.async_get_last_state():
                self._state = state.state == STATE_ON
        await super().async_added_to_hass()

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        if self._template is not None:
            self.add_template_attribute(
                "_state", self._template, None, self._update_state
            )

        super()._async_setup_templates()

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Fire the on action."""
        if on_script := self._action_scripts.get(CONF_TURN_ON):
            await self.async_run_script(on_script, context=self._context)
        if self._template is None:
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Fire the off action."""
        if off_script := self._action_scripts.get(CONF_TURN_OFF):
            await self.async_run_script(off_script, context=self._context)
        if self._template is None:
            self._state = False
            self.async_write_ha_state()


class TriggerSwitchEntity(TriggerEntity, SwitchEntity, RestoreEntity):
    """Switch entity based on trigger data."""

    _entity_id_format = ENTITY_ID_FORMAT
    domain = SWITCH_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        super().__init__(hass, coordinator, config)

        name = self._rendered.get(CONF_NAME, DEFAULT_NAME)
        self._template = config.get(CONF_STATE)
        if on_action := config.get(CONF_TURN_ON):
            self.add_script(CONF_TURN_ON, on_action, name, DOMAIN)
        if off_action := config.get(CONF_TURN_OFF):
            self.add_script(CONF_TURN_OFF, off_action, name, DOMAIN)

        self._attr_assumed_state = self._template is None
        if not self._attr_assumed_state:
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

        if not self._attr_assumed_state:
            raw = self._rendered.get(CONF_STATE)
            self._attr_is_on = template.result_as_boolean(raw)

            self.async_set_context(self.coordinator.data["context"])
            self.async_write_ha_state()
        elif self._attr_assumed_state and len(self._rendered) > 0:
            # In case name, icon, or friendly name have a template but
            # states does not
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Fire the on action."""
        if on_script := self._action_scripts.get(CONF_TURN_ON):
            await self.async_run_script(on_script, context=self._context)
        if self._template is None:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Fire the off action."""
        if off_script := self._action_scripts.get(CONF_TURN_OFF):
            await self.async_run_script(off_script, context=self._context)
        if self._template is None:
            self._attr_is_on = False
            self.async_write_ha_state()
