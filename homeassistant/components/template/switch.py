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
    CONF_STATE,
    CONF_SWITCHES,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_OFF,
    STATE_ON,
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
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_OBJECT_ID, CONF_PICTURE, CONF_TURN_OFF, CONF_TURN_ON, DOMAIN
from .template_entity import (
    LEGACY_FIELDS as TEMPLATE_ENTITY_LEGACY_FIELDS,
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA,
    TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_ICON_SCHEMA,
    TemplateEntity,
    rewrite_common_legacy_to_modern_conf,
)

_VALID_STATES = [STATE_ON, STATE_OFF, "true", "false"]

LEGACY_FIELDS = TEMPLATE_ENTITY_LEGACY_FIELDS | {
    CONF_VALUE_TEMPLATE: CONF_STATE,
}

DEFAULT_NAME = "Template Switch"


SWITCH_SCHEMA = (
    vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.template,
            vol.Optional(CONF_STATE): cv.template,
            vol.Required(CONF_TURN_ON): cv.SCRIPT_SCHEMA,
            vol.Required(CONF_TURN_OFF): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(CONF_PICTURE): cv.template,
        }
    )
    .extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA.schema)
    .extend(TEMPLATE_ENTITY_ICON_SCHEMA.schema)
)

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


def rewrite_legacy_to_modern_conf(
    hass: HomeAssistant, config: dict[str, dict]
) -> list[dict]:
    """Rewrite legacy switch configuration definitions to modern ones."""
    switches = []

    for object_id, entity_conf in config.items():
        entity_conf = {**entity_conf, CONF_OBJECT_ID: object_id}

        entity_conf = rewrite_common_legacy_to_modern_conf(
            hass, entity_conf, LEGACY_FIELDS
        )

        if CONF_NAME not in entity_conf:
            entity_conf[CONF_NAME] = template.Template(object_id, hass)

        switches.append(entity_conf)

    return switches


def rewrite_options_to_modern_conf(option_config: dict[str, dict]) -> dict[str, dict]:
    """Rewrite option configuration to modern configuration."""
    option_config = {**option_config}

    if CONF_VALUE_TEMPLATE in option_config:
        option_config[CONF_STATE] = option_config.pop(CONF_VALUE_TEMPLATE)

    return option_config


@callback
def _async_create_template_tracking_entities(
    async_add_entities: AddEntitiesCallback,
    hass: HomeAssistant,
    definitions: list[dict],
    unique_id_prefix: str | None,
) -> None:
    """Create the template switches."""
    switches = []

    for entity_conf in definitions:
        unique_id = entity_conf.get(CONF_UNIQUE_ID)

        if unique_id and unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"

        switches.append(
            SwitchTemplate(
                hass,
                entity_conf,
                unique_id,
            )
        )

    async_add_entities(switches)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template switches."""
    if discovery_info is None:
        _async_create_template_tracking_entities(
            async_add_entities,
            hass,
            rewrite_legacy_to_modern_conf(hass, config[CONF_SWITCHES]),
            None,
        )
        return

    _async_create_template_tracking_entities(
        async_add_entities,
        hass,
        discovery_info["entities"],
        discovery_info["unique_id"],
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
    async_add_entities([SwitchTemplate(hass, validated_config, config_entry.entry_id)])


@callback
def async_create_preview_switch(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> SwitchTemplate:
    """Create a preview switch."""
    updated_config = rewrite_options_to_modern_conf(config)
    validated_config = SWITCH_CONFIG_SCHEMA(updated_config | {CONF_NAME: name})
    return SwitchTemplate(hass, validated_config, None)


class SwitchTemplate(TemplateEntity, SwitchEntity, RestoreEntity):
    """Representation of a Template switch."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Initialize the Template switch."""
        super().__init__(hass, config=config, fallback_name=None, unique_id=unique_id)
        if (object_id := config.get(CONF_OBJECT_ID)) is not None:
            self.entity_id = async_generate_entity_id(
                ENTITY_ID_FORMAT, object_id, hass=hass
            )
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
