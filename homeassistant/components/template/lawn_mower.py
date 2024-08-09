"""Support for Template lawn mowers."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.lawn_mower import (
    DOMAIN as LAWN_MOWER_DOMAIN,
    SERVICE_DOCK,
    SERVICE_PAUSE,
    SERVICE_START_MOWING,
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .template_entity import (
    TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY,
    TemplateEntity,
    rewrite_common_legacy_to_modern_conf,
)

_LOGGER = logging.getLogger(__name__)

CONF_LAWN_MOWERS = "lawn_mowers"

ENTITY_ID_FORMAT = LAWN_MOWER_DOMAIN + ".{}"
_VALID_STATES = [
    LawnMowerActivity.DOCKED,
    LawnMowerActivity.ERROR,
    LawnMowerActivity.MOWING,
    LawnMowerActivity.PAUSED,
]

LAWN_MOWER_SCHEMA = vol.All(
    cv.deprecated(CONF_ENTITY_ID),
    vol.Schema(
        {
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
            vol.Optional(SERVICE_START_MOWING): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_PAUSE): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_DOCK): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )
    .extend(TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA_LEGACY.schema)
    .extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY.schema),
)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_LAWN_MOWERS): vol.Schema({cv.slug: LAWN_MOWER_SCHEMA})}
)


async def _async_create_entities(hass: HomeAssistant, config: ConfigType):
    """Create the Lawn Mowers."""
    lawn_mowers = []

    for object_id, entity_config in config[CONF_LAWN_MOWERS].items():
        entity_config = rewrite_common_legacy_to_modern_conf(entity_config)
        unique_id = entity_config.get(CONF_UNIQUE_ID)

        lawn_mowers.append(
            TemplateLawnMower(
                hass,
                object_id,
                entity_config,
                unique_id,
            )
        )

    return lawn_mowers


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template lawn mowers."""
    async_add_entities(await _async_create_entities(hass, config))


class TemplateLawnMower(TemplateEntity, LawnMowerEntity):
    """A template lawn mower component."""

    _attr_should_poll = False

    def __init__(
        self,
        hass,
        object_id,
        config,
        unique_id,
    ):
        """Initialize the lawn mower."""
        super().__init__(
            hass, config=config, fallback_name=object_id, unique_id=unique_id
        )
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, object_id, hass=hass
        )
        friendly_name = self._attr_name

        self._template = config.get(CONF_VALUE_TEMPLATE)

        self._start_mowing_script = None
        if start_mowing_action := config.get(SERVICE_START_MOWING):
            self._start_mowing_script = Script(
                hass, start_mowing_action, friendly_name, DOMAIN
            )
            self._attr_supported_features |= LawnMowerEntityFeature.START_MOWING

        self._pause_script = None
        if pause_action := config.get(SERVICE_PAUSE):
            self._pause_script = Script(hass, pause_action, friendly_name, DOMAIN)
            self._attr_supported_features |= LawnMowerEntityFeature.PAUSE

        self._dock_script = None
        if dock_action := config.get(SERVICE_DOCK):
            self._dock_script = Script(hass, dock_action, friendly_name, DOMAIN)
            self._attr_supported_features |= LawnMowerEntityFeature.DOCK

        self._attr_activity = None

    @property
    def activity(self) -> LawnMowerActivity | None:
        """Return the status of the lawn mower."""
        return self._attr_activity

    async def async_start_mowing(self) -> None:
        """Start or resume the mowing task."""
        if self._start_mowing_script is None:
            return
        await self.async_run_script(self._start_mowing_script, context=self._context)

    async def async_pause(self) -> None:
        """Pause the mowing task."""
        if self._pause_script is None:
            return

        await self.async_run_script(self._pause_script, context=self._context)

    async def async_dock(self, **kwargs: Any) -> None:
        """Set the lawn mower to return to the dock."""
        if self._dock_script is None:
            return

        await self.async_run_script(self._dock_script, context=self._context)

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        if self._template is not None:
            self.add_template_attribute(
                "_attr_activity", self._template, None, self._update_state
            )
        super()._async_setup_templates()

    @callback
    def _update_state(self, result):
        super()._update_state(result)
        if isinstance(result, TemplateError):
            # This is legacy behavior
            self._attr_activity = None
            if not self._availability_template:
                self._attr_available = True
            return

        # Validate state
        if result in _VALID_STATES:
            self._attr_activity = LawnMowerActivity(result)
        elif result == STATE_UNKNOWN:
            self._attr_activity = None
        else:
            _LOGGER.error(
                "Received invalid lawn mower state: %s for entity %s. Expected: %s",
                result,
                self.entity_id,
                ", ".join(_VALID_STATES),
            )
            self._attr_activity = None
