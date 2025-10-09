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
from homeassistant.const import CONF_NAME, CONF_STATE, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TriggerUpdateCoordinator
from .const import CONF_MAX, CONF_MIN, CONF_STEP
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA,
    make_template_entity_common_modern_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

CONF_SET_VALUE = "set_value"

DEFAULT_NAME = "Template Number"
DEFAULT_OPTIMISTIC = False

NUMBER_COMMON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MAX, default=DEFAULT_MAX_VALUE): cv.template,
        vol.Optional(CONF_MIN, default=DEFAULT_MIN_VALUE): cv.template,
        vol.Required(CONF_SET_VALUE): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_STATE): cv.template,
        vol.Optional(CONF_STEP, default=DEFAULT_STEP): cv.template,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)

NUMBER_YAML_SCHEMA = NUMBER_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA
).extend(make_template_entity_common_modern_schema(NUMBER_DOMAIN, DEFAULT_NAME).schema)

NUMBER_CONFIG_ENTRY_SCHEMA = NUMBER_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
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
    await async_setup_template_entry(
        hass,
        config_entry,
        async_add_entities,
        StateNumberEntity,
        NUMBER_CONFIG_ENTRY_SCHEMA,
    )


@callback
def async_create_preview_number(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateNumberEntity:
    """Create a preview number."""
    return async_setup_template_preview(
        hass, name, config, StateNumberEntity, NUMBER_CONFIG_ENTRY_SCHEMA
    )


class AbstractTemplateNumber(AbstractTemplateEntity, NumberEntity):
    """Representation of a template number features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(self, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""
        self._step_template = config[CONF_STEP]
        self._min_template = config[CONF_MIN]
        self._max_template = config[CONF_MAX]

        self._attr_native_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
        self._attr_native_step = DEFAULT_STEP
        self._attr_native_min_value = DEFAULT_MIN_VALUE
        self._attr_native_max_value = DEFAULT_MAX_VALUE

    async def async_set_native_value(self, value: float) -> None:
        """Set value of the number."""
        if self._attr_assumed_state:
            self._attr_native_value = value
            self.async_write_ha_state()
        if set_value := self._action_scripts.get(CONF_SET_VALUE):
            await self.async_run_actions(
                set_value,
                run_variables={ATTR_VALUE: value},
                context=self._context,
            )


class StateNumberEntity(TemplateEntity, AbstractTemplateNumber):
    """Representation of a template number."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Initialize the number."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        AbstractTemplateNumber.__init__(self, config)

        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        self.add_actions(CONF_SET_VALUE, config[CONF_SET_VALUE], name)

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        if self._template is not None:
            self.add_template_attribute(
                "_attr_native_value",
                self._template,
                vol.Coerce(float),
                none_on_template_error=True,
            )
        if self._step_template is not None:
            self.add_template_attribute(
                "_attr_native_step",
                self._step_template,
                vol.Coerce(float),
                none_on_template_error=True,
            )
        if self._min_template is not None:
            self.add_template_attribute(
                "_attr_native_min_value",
                self._min_template,
                validator=vol.Coerce(float),
                none_on_template_error=True,
            )
        if self._max_template is not None:
            self.add_template_attribute(
                "_attr_native_max_value",
                self._max_template,
                validator=vol.Coerce(float),
                none_on_template_error=True,
            )
        super()._async_setup_templates()


class TriggerNumberEntity(TriggerEntity, AbstractTemplateNumber):
    """Number entity based on trigger data."""

    domain = NUMBER_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: dict,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        AbstractTemplateNumber.__init__(self, config)

        for key in (
            CONF_STATE,
            CONF_STEP,
            CONF_MIN,
            CONF_MAX,
        ):
            if isinstance(config.get(key), template.Template):
                self._to_render_simple.append(key)
                self._parse_result.add(key)

        self.add_actions(
            CONF_SET_VALUE,
            config[CONF_SET_VALUE],
            self._rendered.get(CONF_NAME, DEFAULT_NAME),
        )

    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self._process_data()

        if not self.available:
            self.async_write_ha_state()
            return

        write_ha_state = False
        for key, attr in (
            (CONF_STATE, "_attr_native_value"),
            (CONF_STEP, "_attr_native_step"),
            (CONF_MIN, "_attr_native_min_value"),
            (CONF_MAX, "_attr_native_max_value"),
        ):
            if (rendered := self._rendered.get(key)) is not None:
                setattr(self, attr, vol.Any(vol.Coerce(float), None)(rendered))
                write_ha_state = True

        if len(self._rendered) > 0:
            # In case any non optimistic template
            write_ha_state = True

        if write_ha_state:
            self.async_set_context(self.coordinator.data["context"])
            self.async_write_ha_state()
