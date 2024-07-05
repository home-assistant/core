"""Support for numbers which integrates with other components."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE,
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    DOMAIN as NUMBER_DOMAIN,
    NumberEntity,
)
from homeassistant.const import CONF_NAME, CONF_OPTIMISTIC, CONF_STATE, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TriggerUpdateCoordinator
from .const import DOMAIN
from .template_entity import (
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA,
    TEMPLATE_ENTITY_ICON_SCHEMA,
    TemplateEntity,
)
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

CONF_SET_VALUE = "set_value"

DEFAULT_NAME = "Template Number"
DEFAULT_OPTIMISTIC = False

NUMBER_SCHEMA = (
    vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.template,
            vol.Required(CONF_STATE): cv.template,
            vol.Required(CONF_SET_VALUE): cv.SCRIPT_SCHEMA,
            vol.Required(ATTR_STEP): cv.template,
            vol.Optional(ATTR_MIN, default=DEFAULT_MIN_VALUE): cv.template,
            vol.Optional(ATTR_MAX, default=DEFAULT_MAX_VALUE): cv.template,
            vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )
    .extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA.schema)
    .extend(TEMPLATE_ENTITY_ICON_SCHEMA.schema)
)


async def _async_create_entities(
    hass: HomeAssistant, definitions: list[dict[str, Any]], unique_id_prefix: str | None
) -> list[TemplateNumber]:
    """Create the Template number."""
    entities = []
    for definition in definitions:
        unique_id = definition.get(CONF_UNIQUE_ID)
        if unique_id and unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"
        entities.append(TemplateNumber(hass, definition, unique_id))
    return entities


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template number."""
    if discovery_info is None:
        _LOGGER.warning(
            "Template number entities can only be configured under template:"
        )
        return

    if "coordinator" in discovery_info:
        async_add_entities(
            TriggerNumberEntity(hass, discovery_info["coordinator"], config)
            for config in discovery_info["entities"]
        )
        return

    async_add_entities(
        await _async_create_entities(
            hass, discovery_info["entities"], discovery_info["unique_id"]
        )
    )


class TemplateNumber(TemplateEntity, NumberEntity):
    """Representation of a template number."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config,
        unique_id: str | None,
    ) -> None:
        """Initialize the number."""
        super().__init__(hass, config=config, unique_id=unique_id)
        assert self._attr_name is not None
        self._value_template = config[CONF_STATE]
        self._command_set_value = Script(
            hass, config[CONF_SET_VALUE], self._attr_name, DOMAIN
        )
        self._step_template = config[ATTR_STEP]
        self._min_value_template = config[ATTR_MIN]
        self._max_value_template = config[ATTR_MAX]
        self._attr_assumed_state = self._optimistic = config[CONF_OPTIMISTIC]
        self._attr_native_step = DEFAULT_STEP
        self._attr_native_min_value = DEFAULT_MIN_VALUE
        self._attr_native_max_value = DEFAULT_MAX_VALUE

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        self.add_template_attribute(
            "_attr_native_value",
            self._value_template,
            validator=vol.Coerce(float),
            none_on_template_error=True,
        )
        self.add_template_attribute(
            "_attr_native_step",
            self._step_template,
            validator=vol.Coerce(float),
            none_on_template_error=True,
        )
        if self._min_value_template is not None:
            self.add_template_attribute(
                "_attr_native_min_value",
                self._min_value_template,
                validator=vol.Coerce(float),
                none_on_template_error=True,
            )
        if self._max_value_template is not None:
            self.add_template_attribute(
                "_attr_native_max_value",
                self._max_value_template,
                validator=vol.Coerce(float),
                none_on_template_error=True,
            )
        super()._async_setup_templates()

    async def async_set_native_value(self, value: float) -> None:
        """Set value of the number."""
        if self._optimistic:
            self._attr_native_value = value
            self.async_write_ha_state()
        await self.async_run_script(
            self._command_set_value,
            run_variables={ATTR_VALUE: value},
            context=self._context,
        )


class TriggerNumberEntity(TriggerEntity, NumberEntity):
    """Number entity based on trigger data."""

    domain = NUMBER_DOMAIN
    extra_template_keys = (
        CONF_STATE,
        ATTR_STEP,
        ATTR_MIN,
        ATTR_MAX,
    )

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: dict,
    ) -> None:
        """Initialize the entity."""
        super().__init__(hass, coordinator, config)
        self._command_set_value = Script(
            hass,
            config[CONF_SET_VALUE],
            self._rendered.get(CONF_NAME, DEFAULT_NAME),
            DOMAIN,
        )

    @property
    def native_value(self) -> float | None:
        """Return the currently selected option."""
        return vol.Any(vol.Coerce(float), None)(self._rendered.get(CONF_STATE))

    @property
    def native_min_value(self) -> int:
        """Return the minimum value."""
        return vol.Any(vol.Coerce(float), None)(
            self._rendered.get(ATTR_MIN, super().native_min_value)
        )

    @property
    def native_max_value(self) -> int:
        """Return the maximum value."""
        return vol.Any(vol.Coerce(float), None)(
            self._rendered.get(ATTR_MAX, super().native_max_value)
        )

    @property
    def native_step(self) -> int:
        """Return the increment/decrement step."""
        return vol.Any(vol.Coerce(float), None)(
            self._rendered.get(ATTR_STEP, super().native_step)
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set value of the number."""
        if self._config[CONF_OPTIMISTIC]:
            self._attr_native_value = value
            self.async_write_ha_state()
        await self._command_set_value.async_run(
            {ATTR_VALUE: value}, context=self._context
        )
