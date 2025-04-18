"""Support for switches which integrates with other components."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.switch import (
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
    CONF_SWITCHES,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_OFF,
    STATE_ON,
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

from .const import CONF_TURN_OFF, CONF_TURN_ON, DOMAIN
from .template_entity import (
    TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY,
    TemplateEntity,
    rewrite_common_legacy_to_modern_conf,
)

_VALID_STATES = [STATE_ON, STATE_OFF, "true", "false"]

SWITCH_SCHEMA = vol.All(
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
    {vol.Required(CONF_SWITCHES): cv.schema_with_slug_keys(SWITCH_SCHEMA)}
)

SWITCH_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.template,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_TURN_ON): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_TURN_OFF): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
    }
)


async def _async_create_entities(hass: HomeAssistant, config: ConfigType):
    """Create the Template switches."""
    switches = []

    for object_id, entity_config in config[CONF_SWITCHES].items():
        entity_config = rewrite_common_legacy_to_modern_conf(hass, entity_config)
        unique_id = entity_config.get(CONF_UNIQUE_ID)

        switches.append(
            SwitchTemplate(
                hass,
                object_id,
                entity_config,
                unique_id,
            )
        )

    return switches


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template switches."""
    async_add_entities(await _async_create_entities(hass, config))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    _options = dict(config_entry.options)
    _options.pop("template_type")
    validated_config = SWITCH_CONFIG_SCHEMA(_options)
    async_add_entities(
        [SwitchTemplate(hass, None, validated_config, config_entry.entry_id)]
    )


@callback
def async_create_preview_switch(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> SwitchTemplate:
    """Create a preview switch."""
    validated_config = SWITCH_CONFIG_SCHEMA(config | {CONF_NAME: name})
    return SwitchTemplate(hass, None, validated_config, None)


class SwitchTemplate(TemplateEntity, SwitchEntity, RestoreEntity):
    """Representation of a Template switch."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        object_id,
        config: ConfigType,
        unique_id,
    ) -> None:
        """Initialize the Template switch."""
        super().__init__(
            hass, config=config, fallback_name=object_id, unique_id=unique_id
        )
        if object_id is not None:
            self.entity_id = async_generate_entity_id(
                ENTITY_ID_FORMAT, object_id, hass=hass
            )
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None
        self._template = config.get(CONF_VALUE_TEMPLATE)

        if on_action := config.get(CONF_TURN_ON):
            self.add_script(CONF_TURN_ON, on_action, name, DOMAIN)
        if off_action := config.get(CONF_TURN_OFF):
            self.add_script(CONF_TURN_OFF, off_action, name, DOMAIN)

        self._state: bool | None = False
        self._attr_assumed_state = self._template is None
        self._attr_device_info = async_device_info_to_link_from_device_id(
            hass,
            config.get(CONF_DEVICE_ID),
        )

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
