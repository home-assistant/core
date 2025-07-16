"""Support for numbers which integrates with other components."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.number import (
    ATTR_VALUE,
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    DOMAIN as NUMBER_DOMAIN,
    ENTITY_ID_FORMAT,
    NumberEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_STATE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TriggerUpdateCoordinator
from .const import CONF_MAX, CONF_MIN, CONF_STEP, DOMAIN
from .helpers import async_setup_template_platform
from .template_entity import TemplateEntity, make_template_entity_common_modern_schema
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

CONF_SET_VALUE = "set_value"

DEFAULT_NAME = "Template Number"
DEFAULT_OPTIMISTIC = False

NUMBER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STATE): cv.template,
        vol.Required(CONF_SET_VALUE): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_STEP): cv.template,
        vol.Optional(CONF_MIN, default=DEFAULT_MIN_VALUE): cv.template,
        vol.Optional(CONF_MAX, default=DEFAULT_MAX_VALUE): cv.template,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    }
).extend(make_template_entity_common_modern_schema(DEFAULT_NAME).schema)
NUMBER_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.template,
        vol.Required(CONF_STATE): cv.template,
        vol.Required(CONF_STEP): cv.template,
        vol.Required(CONF_SET_VALUE): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_MIN): cv.template,
        vol.Optional(CONF_MAX): cv.template,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template number."""
    await async_setup_template_platform(
        hass,
        NUMBER_DOMAIN,
        config,
        StateNumberEntity,
        TriggerNumberEntity,
        async_add_entities,
        discovery_info,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    _options = dict(config_entry.options)
    _options.pop("template_type")
    validated_config = NUMBER_CONFIG_SCHEMA(_options)
    async_add_entities(
        [StateNumberEntity(hass, validated_config, config_entry.entry_id)]
    )


@callback
def async_create_preview_number(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateNumberEntity:
    """Create a preview number."""
    validated_config = NUMBER_CONFIG_SCHEMA(config | {CONF_NAME: name})
    return StateNumberEntity(hass, validated_config, None)


class StateNumberEntity(TemplateEntity, NumberEntity):
    """Representation of a template number."""

    _attr_should_poll = False
    _entity_id_format = ENTITY_ID_FORMAT

    def __init__(
        self,
        hass: HomeAssistant,
        config,
        unique_id: str | None,
    ) -> None:
        """Initialize the number."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        if TYPE_CHECKING:
            assert self._attr_name is not None

        self._value_template = config[CONF_STATE]
        self.add_script(CONF_SET_VALUE, config[CONF_SET_VALUE], self._attr_name, DOMAIN)

        self._step_template = config[CONF_STEP]
        self._min_value_template = config[CONF_MIN]
        self._max_value_template = config[CONF_MAX]
        self._attr_assumed_state = self._optimistic = config.get(CONF_OPTIMISTIC)
        self._attr_native_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
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
        if set_value := self._action_scripts.get(CONF_SET_VALUE):
            await self.async_run_script(
                set_value,
                run_variables={ATTR_VALUE: value},
                context=self._context,
            )


class TriggerNumberEntity(TriggerEntity, NumberEntity):
    """Number entity based on trigger data."""

    _entity_id_format = ENTITY_ID_FORMAT
    domain = NUMBER_DOMAIN
    extra_template_keys = (
        CONF_STATE,
        CONF_STEP,
        CONF_MIN,
        CONF_MAX,
    )

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: dict,
    ) -> None:
        """Initialize the entity."""
        super().__init__(hass, coordinator, config)

        name = self._rendered.get(CONF_NAME, DEFAULT_NAME)
        self.add_script(CONF_SET_VALUE, config[CONF_SET_VALUE], name, DOMAIN)

        self._attr_native_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)

    @property
    def native_value(self) -> float | None:
        """Return the currently selected option."""
        return vol.Any(vol.Coerce(float), None)(self._rendered.get(CONF_STATE))

    @property
    def native_min_value(self) -> int:
        """Return the minimum value."""
        return vol.Any(vol.Coerce(float), None)(
            self._rendered.get(CONF_MIN, super().native_min_value)
        )

    @property
    def native_max_value(self) -> int:
        """Return the maximum value."""
        return vol.Any(vol.Coerce(float), None)(
            self._rendered.get(CONF_MAX, super().native_max_value)
        )

    @property
    def native_step(self) -> int:
        """Return the increment/decrement step."""
        return vol.Any(vol.Coerce(float), None)(
            self._rendered.get(CONF_STEP, super().native_step)
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set value of the number."""
        if self._config[CONF_OPTIMISTIC]:
            self._attr_native_value = value
            self.async_write_ha_state()
        if set_value := self._action_scripts.get(CONF_SET_VALUE):
            await self.async_run_script(
                set_value,
                run_variables={ATTR_VALUE: value},
                context=self._context,
            )
