"""Support for Template fans."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN as FAN_DOMAIN,
    ENTITY_ID_FORMAT,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_NAME,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import validators as template_validators
from .const import DOMAIN
from .coordinator import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA,
    make_template_entity_common_modern_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

CONF_FANS = "fans"
CONF_SPEED_COUNT = "speed_count"
CONF_PRESET_MODES = "preset_modes"
CONF_PERCENTAGE_TEMPLATE = "percentage_template"
CONF_PRESET_MODE_TEMPLATE = "preset_mode_template"
CONF_OSCILLATING_TEMPLATE = "oscillating_template"
CONF_DIRECTION_TEMPLATE = "direction_template"
CONF_ON_ACTION = "turn_on"
CONF_OFF_ACTION = "turn_off"
CONF_SET_PERCENTAGE_ACTION = "set_percentage"
CONF_SET_OSCILLATING_ACTION = "set_oscillating"
CONF_SET_DIRECTION_ACTION = "set_direction"
CONF_SET_PRESET_MODE_ACTION = "set_preset_mode"

_VALID_DIRECTIONS = [DIRECTION_FORWARD, DIRECTION_REVERSE]

CONF_DIRECTION = "direction"
CONF_OSCILLATING = "oscillating"
CONF_PERCENTAGE = "percentage"
CONF_PRESET_MODE = "preset_mode"

LEGACY_FIELDS = {
    CONF_DIRECTION_TEMPLATE: CONF_DIRECTION,
    CONF_OSCILLATING_TEMPLATE: CONF_OSCILLATING,
    CONF_PERCENTAGE_TEMPLATE: CONF_PERCENTAGE,
    CONF_PRESET_MODE_TEMPLATE: CONF_PRESET_MODE,
    CONF_VALUE_TEMPLATE: CONF_STATE,
}

DEFAULT_NAME = "Template Fan"

FAN_COMMON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DIRECTION): cv.template,
        vol.Required(CONF_OFF_ACTION): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_OSCILLATING): cv.template,
        vol.Optional(CONF_PERCENTAGE): cv.template,
        vol.Optional(CONF_PRESET_MODE): cv.template,
        vol.Optional(CONF_PRESET_MODES): cv.ensure_list,
        vol.Optional(CONF_SET_DIRECTION_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_OSCILLATING_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_PERCENTAGE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_PRESET_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SPEED_COUNT): vol.Coerce(int),
        vol.Optional(CONF_STATE): cv.template,
    }
)

FAN_YAML_SCHEMA = FAN_COMMON_SCHEMA.extend(TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA).extend(
    make_template_entity_common_modern_schema(FAN_DOMAIN, DEFAULT_NAME).schema
)

FAN_LEGACY_YAML_SCHEMA = vol.All(
    cv.deprecated(CONF_ENTITY_ID),
    vol.Schema(
        {
            vol.Optional(CONF_DIRECTION_TEMPLATE): cv.template,
            vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Required(CONF_OFF_ACTION): cv.SCRIPT_SCHEMA,
            vol.Required(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_OSCILLATING_TEMPLATE): cv.template,
            vol.Optional(CONF_PERCENTAGE_TEMPLATE): cv.template,
            vol.Optional(CONF_PRESET_MODE_TEMPLATE): cv.template,
            vol.Optional(CONF_PRESET_MODES): cv.ensure_list,
            vol.Optional(CONF_SET_DIRECTION_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_SET_OSCILLATING_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_SET_PERCENTAGE_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_SET_PRESET_MODE_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_SPEED_COUNT): vol.Coerce(int),
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        }
    ).extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY.schema),
)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_FANS): cv.schema_with_slug_keys(FAN_LEGACY_YAML_SCHEMA)}
)

FAN_CONFIG_ENTRY_SCHEMA = FAN_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template fans."""
    await async_setup_template_platform(
        hass,
        FAN_DOMAIN,
        config,
        StateFanEntity,
        TriggerFanEntity,
        async_add_entities,
        discovery_info,
        LEGACY_FIELDS,
        legacy_key=CONF_FANS,
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
        StateFanEntity,
        FAN_CONFIG_ENTRY_SCHEMA,
    )


@callback
def async_create_preview_fan(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateFanEntity:
    """Create a preview."""
    return async_setup_template_preview(
        hass,
        name,
        config,
        StateFanEntity,
        FAN_CONFIG_ENTRY_SCHEMA,
    )


class AbstractTemplateFan(AbstractTemplateEntity, FanEntity):
    """Representation of a template fan features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(self, name: str, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""
        self.setup_state_template(
            CONF_STATE,
            "_attr_is_on",
            template_validators.boolean(self, CONF_STATE),
        )

        # Ensure legacy template entity functionality by setting percentage to None instead
        # of the FanEntity default of 0.
        self._attr_percentage = None
        self.setup_template(
            CONF_PERCENTAGE,
            "_attr_percentage",
            template_validators.number(self, CONF_PERCENTAGE, 0, 100),
        )

        # List of valid preset modes
        self._attr_preset_modes: list[str] | None = config.get(CONF_PRESET_MODES)
        self.setup_template(
            CONF_PRESET_MODE,
            "_attr_preset_mode",
            template_validators.item_in_list(
                self, CONF_PRESET_MODE, self._attr_preset_modes
            ),
        )

        # Oscillating boolean
        self.setup_template(
            CONF_OSCILLATING,
            "_attr_oscillating",
            template_validators.boolean(self, CONF_OSCILLATING),
        )

        # Forward/Reverse Directions
        self.setup_template(
            CONF_DIRECTION,
            "_attr_current_direction",
            template_validators.item_in_list(self, CONF_DIRECTION, _VALID_DIRECTIONS),
        )

        # Number of valid speeds
        self._attr_speed_count = config.get(CONF_SPEED_COUNT) or 100

        self._attr_supported_features |= (
            FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON
        )
        for action_id, supported_feature in (
            (CONF_ON_ACTION, 0),
            (CONF_OFF_ACTION, 0),
            (CONF_SET_PERCENTAGE_ACTION, FanEntityFeature.SET_SPEED),
            (CONF_SET_PRESET_MODE_ACTION, FanEntityFeature.PRESET_MODE),
            (CONF_SET_OSCILLATING_ACTION, FanEntityFeature.OSCILLATE),
            (CONF_SET_DIRECTION_ACTION, FanEntityFeature.DIRECTION),
        ):
            if (action_config := config.get(action_id)) is not None:
                self.add_script(action_id, action_config, name, DOMAIN)
                self._attr_supported_features |= supported_feature

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._attr_is_on

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        await self.async_run_script(
            self._action_scripts[CONF_ON_ACTION],
            run_variables={
                ATTR_PERCENTAGE: percentage,
                ATTR_PRESET_MODE: preset_mode,
            },
            context=self._context,
        )

        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        if percentage is not None:
            await self.async_set_percentage(percentage)

        if self._attr_assumed_state:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.async_run_script(
            self._action_scripts[CONF_OFF_ACTION], context=self._context
        )

        if self._attr_assumed_state:
            self._attr_is_on = False
            self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage speed of the fan."""
        self._attr_percentage = percentage

        if script := self._action_scripts.get(CONF_SET_PERCENTAGE_ACTION):
            await self.async_run_script(
                script,
                run_variables={ATTR_PERCENTAGE: self._attr_percentage},
                context=self._context,
            )

        if self._attr_assumed_state:
            self._attr_is_on = percentage != 0

        if self._attr_assumed_state or CONF_PERCENTAGE not in self._templates:
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset_mode of the fan."""
        self._attr_preset_mode = preset_mode

        if script := self._action_scripts.get(CONF_SET_PRESET_MODE_ACTION):
            await self.async_run_script(
                script,
                run_variables={ATTR_PRESET_MODE: self._attr_preset_mode},
                context=self._context,
            )

        if self._attr_assumed_state:
            self._attr_is_on = True

        if self._attr_assumed_state or CONF_PRESET_MODE not in self._templates:
            self.async_write_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation of the fan."""
        self._attr_oscillating = oscillating
        if (
            script := self._action_scripts.get(CONF_SET_OSCILLATING_ACTION)
        ) is not None:
            await self.async_run_script(
                script,
                run_variables={ATTR_OSCILLATING: self.oscillating},
                context=self._context,
            )

        if CONF_OSCILLATING not in self._templates:
            self.async_write_ha_state()

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        if direction in _VALID_DIRECTIONS:
            self._attr_current_direction = direction
            if (
                script := self._action_scripts.get(CONF_SET_DIRECTION_ACTION)
            ) is not None:
                await self.async_run_script(
                    script,
                    run_variables={ATTR_DIRECTION: direction},
                    context=self._context,
                )
            if CONF_DIRECTION not in self._templates:
                self.async_write_ha_state()
        else:
            _LOGGER.error(
                "Received invalid direction: %s for entity %s. Expected: %s",
                direction,
                self.entity_id,
                ", ".join(_VALID_DIRECTIONS),
            )


class StateFanEntity(TemplateEntity, AbstractTemplateFan):
    """A template fan component."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id,
    ) -> None:
        """Initialize the fan."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None
        AbstractTemplateFan.__init__(self, name, config)


class TriggerFanEntity(TriggerEntity, AbstractTemplateFan):
    """Fan entity based on trigger data."""

    domain = FAN_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)
        AbstractTemplateFan.__init__(self, name, config)
