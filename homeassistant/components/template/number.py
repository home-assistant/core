"""Support for numbers which integrates with other components."""
from __future__ import annotations

import contextlib
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.number import NumberEntity
from homeassistant.components.number.const import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE,
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DOMAIN as NUMBER_DOMAIN,
)
from homeassistant.components.template import TriggerUpdateCoordinator
from homeassistant.const import CONF_NAME, CONF_OPTIMISTIC, CONF_STATE, CONF_UNIQUE_ID
from homeassistant.core import Config, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.script import Script
from homeassistant.helpers.template import Template, TemplateError

from .const import CONF_AVAILABILITY
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

CONF_SET_VALUE = "set_value"

DEFAULT_NAME = "Template Number"
DEFAULT_OPTIMISTIC = False

NUMBER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.template,
        vol.Required(CONF_STATE): cv.template,
        vol.Required(CONF_SET_VALUE): cv.SCRIPT_SCHEMA,
        vol.Required(ATTR_STEP): cv.template,
        vol.Optional(ATTR_MIN, default=DEFAULT_MIN_VALUE): cv.template,
        vol.Optional(ATTR_MAX, default=DEFAULT_MAX_VALUE): cv.template,
        vol.Optional(CONF_AVAILABILITY): cv.template,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
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
        entities.append(
            TemplateNumber(
                hass,
                definition[CONF_NAME],
                definition[CONF_STATE],
                definition.get(CONF_AVAILABILITY),
                definition[CONF_SET_VALUE],
                definition[ATTR_STEP],
                definition[ATTR_MIN],
                definition[ATTR_MAX],
                definition[CONF_OPTIMISTIC],
                unique_id,
            )
        )
    return entities


async def async_setup_platform(
    hass: HomeAssistant,
    config: Config,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
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

    def __init__(
        self,
        hass: HomeAssistant,
        name_template: Template,
        value_template: Template,
        availability_template: Template | None,
        command_set_value: dict[str, Any],
        step_template: Template,
        minimum_template: Template | None,
        maximum_template: Template | None,
        optimistic: bool,
        unique_id: str | None,
    ) -> None:
        """Initialize the number."""
        super().__init__(availability_template=availability_template)
        self._attr_name = DEFAULT_NAME
        self._name_template = name_template
        name_template.hass = hass
        with contextlib.suppress(TemplateError):
            self._attr_name = name_template.async_render(parse_result=False)
        self._value_template = value_template
        domain = __name__.split(".")[-2]
        self._command_set_value = Script(
            hass, command_set_value, self._attr_name, domain
        )
        self._step_template = step_template
        self._min_value_template = minimum_template
        self._max_value_template = maximum_template
        self._attr_assumed_state = self._optimistic = optimistic
        self._attr_unique_id = unique_id
        self._attr_value = None
        self._attr_step = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        if self._name_template and not self._name_template.is_static:
            self.add_template_attribute("_attr_name", self._name_template, cv.string)
        self.add_template_attribute(
            "_attr_value",
            self._value_template,
            validator=vol.Coerce(float),
            none_on_template_error=True,
        )
        self.add_template_attribute(
            "_attr_step",
            self._step_template,
            validator=vol.Coerce(float),
            none_on_template_error=True,
        )
        if self._min_value_template is not None:
            self.add_template_attribute(
                "_attr_min_value",
                self._min_value_template,
                validator=vol.Coerce(float),
                none_on_template_error=True,
            )
        if self._max_value_template is not None:
            self.add_template_attribute(
                "_attr_max_value",
                self._max_value_template,
                validator=vol.Coerce(float),
                none_on_template_error=True,
            )
        await super().async_added_to_hass()

    async def async_set_value(self, value: float) -> None:
        """Set value of the number."""
        if self._optimistic:
            self._attr_value = value
            self.async_write_ha_state()
        await self._command_set_value.async_run(
            {ATTR_VALUE: value}, context=self._context
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
        domain = __name__.split(".")[-2]
        self._command_set_value = Script(
            hass,
            config[CONF_SET_VALUE],
            self._rendered.get(CONF_NAME, DEFAULT_NAME),
            domain,
        )

    @property
    def value(self) -> float | None:
        """Return the currently selected option."""
        return vol.Any(vol.Coerce(float), None)(self._rendered.get(CONF_STATE))

    @property
    def min_value(self) -> int:
        """Return the minimum value."""
        return vol.Any(vol.Coerce(float), None)(
            self._rendered.get(ATTR_MIN, super().min_value)
        )

    @property
    def max_value(self) -> int:
        """Return the maximum value."""
        return vol.Any(vol.Coerce(float), None)(
            self._rendered.get(ATTR_MAX, super().max_value)
        )

    @property
    def step(self) -> int:
        """Return the increment/decrement step."""
        return vol.Any(vol.Coerce(float), None)(
            self._rendered.get(ATTR_STEP, super().step)
        )

    async def async_set_value(self, value: float) -> None:
        """Set value of the number."""
        if self._config[CONF_OPTIMISTIC]:
            self._attr_value = value
            self.async_write_ha_state()
        await self._command_set_value.async_run(
            {ATTR_VALUE: value}, context=self._context
        )
