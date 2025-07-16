"""Support for selects which integrates with other components."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    ENTITY_ID_FORMAT,
    SelectEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_NAME, CONF_OPTIMISTIC, CONF_STATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TriggerUpdateCoordinator
from .const import DOMAIN
from .entity import AbstractTemplateEntity
from .helpers import async_setup_template_platform
from .template_entity import TemplateEntity, make_template_entity_common_modern_schema
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

CONF_OPTIONS = "options"
CONF_SELECT_OPTION = "select_option"

DEFAULT_NAME = "Template Select"
DEFAULT_OPTIMISTIC = False

SELECT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_STATE): cv.template,
        vol.Required(CONF_SELECT_OPTION): cv.SCRIPT_SCHEMA,
        vol.Required(ATTR_OPTIONS): cv.template,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    }
).extend(make_template_entity_common_modern_schema(DEFAULT_NAME).schema)


SELECT_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.template,
        vol.Required(CONF_STATE): cv.template,
        vol.Required(CONF_OPTIONS): cv.template,
        vol.Optional(CONF_SELECT_OPTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template select."""
    await async_setup_template_platform(
        hass,
        SELECT_DOMAIN,
        config,
        TemplateSelect,
        TriggerSelectEntity,
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
    validated_config = SELECT_CONFIG_SCHEMA(_options)
    async_add_entities([TemplateSelect(hass, validated_config, config_entry.entry_id)])


class AbstractTemplateSelect(AbstractTemplateEntity, SelectEntity):
    """Representation of a template select features."""

    _entity_id_format = ENTITY_ID_FORMAT

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(self, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""
        self._template = config.get(CONF_STATE)

        self._options_template = config[ATTR_OPTIONS]

        self._attr_assumed_state = self._optimistic = (
            self._template is None or config.get(CONF_OPTIMISTIC, DEFAULT_OPTIMISTIC)
        )
        self._attr_options = []
        self._attr_current_option = None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if self._optimistic:
            self._attr_current_option = option
            self.async_write_ha_state()
        if select_option := self._action_scripts.get(CONF_SELECT_OPTION):
            await self.async_run_script(
                select_option,
                run_variables={ATTR_OPTION: option},
                context=self._context,
            )


class TemplateSelect(TemplateEntity, AbstractTemplateSelect):
    """Representation of a template select."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the select."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        AbstractTemplateSelect.__init__(self, config)

        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        if (select_option := config.get(CONF_SELECT_OPTION)) is not None:
            self.add_script(CONF_SELECT_OPTION, select_option, name, DOMAIN)

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        if self._template is not None:
            self.add_template_attribute(
                "_attr_current_option",
                self._template,
                validator=cv.string,
                none_on_template_error=True,
            )
        self.add_template_attribute(
            "_attr_options",
            self._options_template,
            validator=vol.All(cv.ensure_list, [cv.string]),
            none_on_template_error=True,
        )
        super()._async_setup_templates()


class TriggerSelectEntity(TriggerEntity, AbstractTemplateSelect):
    """Select entity based on trigger data."""

    domain = SELECT_DOMAIN
    extra_template_keys_complex = (ATTR_OPTIONS,)

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: dict,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        AbstractTemplateSelect.__init__(self, config)

        if CONF_STATE in config:
            self._to_render_simple.append(CONF_STATE)

        # Scripts can be an empty list, therefore we need to check for None
        if (select_option := config.get(CONF_SELECT_OPTION)) is not None:
            self.add_script(
                CONF_SELECT_OPTION,
                select_option,
                self._rendered.get(CONF_NAME, DEFAULT_NAME),
                DOMAIN,
            )

    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self._process_data()

        if not self.available:
            self.async_write_ha_state()
            return

        write_ha_state = False
        if (options := self._rendered.get(ATTR_OPTIONS)) is not None:
            self._attr_options = vol.All(cv.ensure_list, [cv.string])(options)
            write_ha_state = True

        if (state := self._rendered.get(CONF_STATE)) is not None:
            self._attr_current_option = cv.string(state)
            write_ha_state = True

        if len(self._rendered) > 0:
            # In case any non optimistic template
            write_ha_state = True

        if write_ha_state:
            self.async_write_ha_state()
