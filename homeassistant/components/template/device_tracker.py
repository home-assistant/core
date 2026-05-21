"""Support for device trackers which integrates with other components."""

from typing import Any

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    ENTITY_ID_FORMAT,
    TrackerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TriggerUpdateCoordinator, validators as template_validators
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    make_template_entity_common_modern_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

DEFAULT_NAME = "Template Device Tracker"

CONF_LOCATION_ACCURACY = "location_accuracy"

TRACKER_COMMON_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LATITUDE): cv.template,
        vol.Optional(CONF_LOCATION_ACCURACY): cv.template,
        vol.Required(CONF_LONGITUDE): cv.template,
    }
)

TRACKER_YAML_SCHEMA = TRACKER_COMMON_SCHEMA.extend(
    make_template_entity_common_modern_schema(
        DEVICE_TRACKER_DOMAIN, DEFAULT_NAME
    ).schema
)


TRACKER_CONFIG_ENTRY_SCHEMA = TRACKER_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template device trackers."""
    await async_setup_template_platform(
        hass,
        DEVICE_TRACKER_DOMAIN,
        config,
        StateTrackerEntity,
        TriggerTrackerEntity,
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
        StateTrackerEntity,
        TRACKER_CONFIG_ENTRY_SCHEMA,
    )


@callback
def async_create_preview_tracker(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateTrackerEntity:
    """Create a preview device tracker."""
    return async_setup_template_preview(
        hass,
        name,
        config,
        StateTrackerEntity,
        TRACKER_CONFIG_ENTRY_SCHEMA,
    )


class AbstractTemplateTracker(AbstractTemplateEntity, TrackerEntity):
    """Representation of a template device tracker features."""

    _entity_id_format = ENTITY_ID_FORMAT

    # The super init is not called because TemplateEntity
    # and TriggerEntity will call
    # AbstractTemplateEntity.__init__. This ensures that
    # the __init__ on AbstractTemplateEntity is not
    # called twice.
    def __init__(self) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""

        self.setup_template(
            CONF_LATITUDE,
            "_attr_latitude",
            template_validators.number(self, CONF_LATITUDE, -90.0, 90.0),
        )
        self.setup_template(
            CONF_LONGITUDE,
            "_attr_longitude",
            template_validators.number(self, CONF_LONGITUDE, -180.0, 180.0),
        )
        self.setup_template(
            CONF_LOCATION_ACCURACY,
            "_attr_location_accuracy",
            on_update=self._update_location_accuracy,
            none_on_template_error=False,
        )

    def _update_location_accuracy(self, value: float | None) -> None:
        """Update the location accuracy."""
        self._attr_location_accuracy = (
            template_validators.number(self, CONF_LOCATION_ACCURACY, 0.0)(value) or 0.0
        )


class StateTrackerEntity(TemplateEntity, AbstractTemplateTracker):
    """Representation of a Template device tracker."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Initialize the Template device tracker."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        AbstractTemplateTracker.__init__(self)


class TriggerTrackerEntity(TriggerEntity, AbstractTemplateTracker):
    """Tracker entity based on trigger data."""

    domain = DEVICE_TRACKER_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        AbstractTemplateTracker.__init__(self)
