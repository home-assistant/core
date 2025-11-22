"""Support for events which integrates with other components."""

from __future__ import annotations

import logging
from typing import Any, Final

import voluptuous as vol

from homeassistant.components.event import (
    DOMAIN as EVENT_DOMAIN,
    ENTITY_ID_FORMAT,
    EventDeviceClass,
    EventEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    make_template_entity_common_modern_attributes_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Template Event"

CONF_EVENT_TYPE = "event_type"
CONF_EVENT_TYPES = "event_types"

DEVICE_CLASS_SCHEMA: Final = vol.All(vol.Lower, vol.Coerce(EventDeviceClass))

EVENT_COMMON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASS_SCHEMA,
        vol.Required(CONF_EVENT_TYPE): cv.template,
        vol.Required(CONF_EVENT_TYPES): cv.template,
    }
)

EVENT_YAML_SCHEMA = EVENT_COMMON_SCHEMA.extend(
    make_template_entity_common_modern_attributes_schema(
        EVENT_DOMAIN, DEFAULT_NAME
    ).schema
)


EVENT_CONFIG_ENTRY_SCHEMA = EVENT_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template event."""
    await async_setup_template_platform(
        hass,
        EVENT_DOMAIN,
        config,
        StateEventEntity,
        TriggerEventEntity,
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
        StateEventEntity,
        EVENT_CONFIG_ENTRY_SCHEMA,
        True,
    )


@callback
def async_create_preview_event(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateEventEntity:
    """Create a preview event."""
    return async_setup_template_preview(
        hass,
        name,
        config,
        StateEventEntity,
        EVENT_CONFIG_ENTRY_SCHEMA,
    )


class AbstractTemplateEvent(AbstractTemplateEntity, EventEntity):
    """Representation of a template event features."""

    _entity_id_format = ENTITY_ID_FORMAT

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(self, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""
        self._event_type_template = config[CONF_EVENT_TYPE]
        self._event_types_template = config[CONF_EVENT_TYPES]

        self._attr_device_class = config.get(CONF_DEVICE_CLASS)

        self._event_type = None
        self._attr_event_types = []

    @callback
    def _update_event_types(self, event_types: Any) -> None:
        """Update the event types from the template."""
        if event_types in (None, "None", ""):
            self._attr_event_types = []
            return

        if not isinstance(event_types, list):
            _LOGGER.error(
                ("Received invalid event_types list: %s for entity %s. Expected list"),
                event_types,
                self.entity_id,
            )
            self._attr_event_types = []
            return

        self._attr_event_types = [str(event_type) for event_type in event_types]

    @callback
    def _update_event_type(self, event_type: Any) -> None:
        """Update the effect from the template."""
        try:
            self._trigger_event(event_type)
        except ValueError:
            _LOGGER.error(
                "Received invalid event_type: %s for entity %s. Expected one of: %s",
                event_type,
                self.entity_id,
                self._attr_event_types,
            )


class StateEventEntity(TemplateEntity, AbstractTemplateEvent):
    """Representation of a template event."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the select."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        AbstractTemplateEvent.__init__(self, config)

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        self.add_template_attribute(
            "_attr_event_types",
            self._event_types_template,
            None,
            self._update_event_types,
            none_on_template_error=True,
        )
        self.add_template_attribute(
            "_event_type",
            self._event_type_template,
            None,
            self._update_event_type,
            none_on_template_error=True,
        )
        super()._async_setup_templates()


class TriggerEventEntity(TriggerEntity, AbstractTemplateEvent, RestoreEntity):
    """Event entity based on trigger data."""

    domain = EVENT_DOMAIN
    extra_template_keys_complex = (
        CONF_EVENT_TYPE,
        CONF_EVENT_TYPES,
    )

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        AbstractTemplateEvent.__init__(self, config)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update of the data."""
        self._process_data()

        if not self.available:
            self.async_write_ha_state()
            return

        for key, updater in (
            (CONF_EVENT_TYPES, self._update_event_types),
            (CONF_EVENT_TYPE, self._update_event_type),
        ):
            updater(self._rendered[key])

        self.async_set_context(self.coordinator.data["context"])
        self.async_write_ha_state()
