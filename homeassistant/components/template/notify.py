"""Support for notify which integrates with other components."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.device import async_device_info_to_link_from_device_id
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .coordinator import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity
from .template_entity import TemplateEntity, make_template_entity_common_modern_schema
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Template Notify"

CONF_SEND_MESSAGE = "send_message"

NOTIFY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SEND_MESSAGE): cv.SCRIPT_SCHEMA,
    }
).extend(make_template_entity_common_modern_schema(DEFAULT_NAME).schema)

NOTIFY_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
        vol.Required(CONF_NAME): cv.template,
        vol.Required(CONF_SEND_MESSAGE): cv.SCRIPT_SCHEMA,
    }
)


async def _async_create_entities(
    hass: HomeAssistant, definitions: list[dict[str, Any]], unique_id_prefix: str | None
) -> list[TemplateNotify]:
    """Create the Template notify."""
    entities = []
    for definition in definitions:
        unique_id = definition.get(CONF_UNIQUE_ID)
        if unique_id and unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"
        entities.append(TemplateNotify(hass, definition, unique_id))
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
            "Template notify entities can only be configured under template:"
        )
        return

    if "coordinator" in discovery_info:
        async_add_entities(
            TriggerNotifyEntity(hass, discovery_info["coordinator"], config)
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
    validated_config = NOTIFY_CONFIG_SCHEMA(_options)
    async_add_entities([TemplateNotify(hass, validated_config, config_entry.entry_id)])


class AbstractTemplateNotify(AbstractTemplateEntity, NotifyEntity):
    """Representation of a template notify features."""

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(self) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""

        self._attr_supported_features: NotifyEntityFeature = NotifyEntityFeature.TITLE

    async def async_send_message(self, message, title=None):
        """Send a message."""
        title = {ATTR_TITLE: title} if title is not None else {}
        await self.async_run_script(
            self._action_scripts[CONF_SEND_MESSAGE],
            run_variables={ATTR_MESSAGE: message, **title},
            context=self._context,
        )


class TemplateNotify(TemplateEntity, AbstractTemplateNotify):
    """Representation of a template notify."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the notify."""
        TemplateEntity.__init__(self, hass, config=config, unique_id=unique_id)
        AbstractTemplateNotify.__init__(self)
        if TYPE_CHECKING:
            assert self._attr_name is not None
        name = self._attr_name

        if (action_config := config.get(CONF_SEND_MESSAGE)) is not None:
            self.add_script(CONF_SEND_MESSAGE, action_config, name, DOMAIN)

        self._attr_device_info = async_device_info_to_link_from_device_id(
            hass, config.get(CONF_DEVICE_ID)
        )


class TriggerNotifyEntity(TriggerEntity, AbstractTemplateNotify):
    """Notify entity based on trigger data."""

    domain = NOTIFY_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        AbstractTemplateNotify.__init__(self)

        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)

        if (action_config := config.get(CONF_SEND_MESSAGE)) is not None:
            self.add_script(CONF_SEND_MESSAGE, action_config, name, DOMAIN)

        self._attr_device_info = async_device_info_to_link_from_device_id(
            hass, config.get(CONF_DEVICE_ID)
        )
