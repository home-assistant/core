"""Support for events which integrates with other components."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

import voluptuous as vol

from homeassistant.components.event import (
    DOMAIN as EVENT_DOMAIN,
    EventDeviceClass,
    EventEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.device import async_device_info_to_link_from_device_id
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TriggerUpdateCoordinator
from .const import CONF_PICTURE
from .entity import AbstractTemplateEntity
from .template_entity import (
    TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA,
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA,
    TEMPLATE_ENTITY_ICON_SCHEMA,
    TemplateEntity,
)
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Template Event"

CONF_EVENT_TYPE = "event_type"
CONF_EVENT_TYPES = "event_types"

DEVICE_CLASS_SCHEMA: Final = vol.All(vol.Lower, vol.Coerce(EventDeviceClass))

EVENT_SCHEMA = (
    vol.Schema(
        {
            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASS_SCHEMA,
            vol.Required(CONF_EVENT_TYPE): cv.template,
            vol.Required(CONF_EVENT_TYPES): cv.template,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.template,
            vol.Optional(CONF_PICTURE): cv.template,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )
    .extend(TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA.schema)
    .extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA.schema)
    .extend(TEMPLATE_ENTITY_ICON_SCHEMA.schema)
)

EVENT_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASS_SCHEMA,
        vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
        vol.Required(CONF_EVENT_TYPE): cv.template,
        vol.Required(CONF_EVENT_TYPES): cv.template,
        vol.Required(CONF_NAME): cv.template,
    }
)


async def _async_create_entities(
    hass: HomeAssistant, definitions: list[dict[str, Any]], unique_id_prefix: str | None
) -> list[TemplateEvent]:
    """Create the Template event."""
    entities = []
    for definition in definitions:
        unique_id = definition.get(CONF_UNIQUE_ID)
        if unique_id and unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"
        entities.append(TemplateEvent(hass, definition, unique_id))
    return entities


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template select."""
    if discovery_info is None:
        _LOGGER.warning(
            "Template event entities can only be configured under template:"
        )
        return

    if "coordinator" in discovery_info:
        async_add_entities(
            TriggerEventEntity(hass, discovery_info["coordinator"], config)
            for config in discovery_info["entities"]
        )
        return

    async_add_entities(
        await _async_create_entities(
            hass, discovery_info["entities"], discovery_info["unique_id"]
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    _options = dict(config_entry.options)
    _options.pop("template_type")
    validated_config = EVENT_CONFIG_SCHEMA(_options)
    async_add_entities([TemplateEvent(hass, validated_config, config_entry.entry_id)])


class AbstractTemplateEvent(AbstractTemplateEntity, EventEntity):
    """Representation of a template event features."""

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
                (
                    "Received invalid event_types list: %s for entity %s. Expected list of"
                    " strings"
                ),
                event_types,
                self.entity_id,
            )
            self._attr_event_types = []
            return

        self._attr_event_types = event_types

    @callback
    def _update_event_type(self, event_type: Any) -> None:
        """Update the effect from the template."""
        try:
            self._trigger_event(event_type, {})
        except ValueError:
            _LOGGER.error(
                "Received invalid event_type: %s for entity %s. Expected one of: %s",
                event_type,
                self.entity_id,
                self._attr_event_types,
            )


class TemplateEvent(TemplateEntity, AbstractTemplateEvent):
    """Representation of a template event."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the select."""
        TemplateEntity.__init__(self, hass, config=config, unique_id=unique_id)
        AbstractTemplateEvent.__init__(self, config)
        if TYPE_CHECKING:
            assert self._attr_name is not None

        self._attr_device_info = async_device_info_to_link_from_device_id(
            hass, config.get(CONF_DEVICE_ID)
        )

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

        # Render the _attr_name before initializing TriggerEventEntity
        self._attr_name = self._rendered.get(CONF_NAME, DEFAULT_NAME)

        self._attr_device_info = async_device_info_to_link_from_device_id(
            hass, config.get(CONF_DEVICE_ID)
        )

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
