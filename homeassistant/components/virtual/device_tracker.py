"""This component provides support for a virtual device tracker."""

from collections.abc import Callable
import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as PLATFORM_DOMAIN,
    SourceType,
    TrackerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.typing import HomeAssistantType

from . import get_entity_configs, get_entity_from_domain
from .const import *
from .entity import VirtualEntity, virtual_schema

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = [COMPONENT_DOMAIN]

CONF_LOCATION = "location"
DEFAULT_DEVICE_TRACKER_VALUE = "home"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    virtual_schema(DEFAULT_DEVICE_TRACKER_VALUE, {})
)
DEVICE_TRACKER_SCHEMA = vol.Schema(virtual_schema(DEFAULT_DEVICE_TRACKER_VALUE, {}))

SERVICE_MOVE = "move"
SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Required(CONF_LOCATION): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> None:
    _LOGGER.debug("setting up the device_tracker entries...")

    entities = []
    for entity in get_entity_configs(
        hass, entry.data[ATTR_GROUP_NAME], PLATFORM_DOMAIN
    ):
        entity = DEVICE_TRACKER_SCHEMA(entity)
        entities.append(VirtualDeviceTracker(entity))
    async_add_entities(entities)

    async def async_virtual_service(call):
        """Call virtual service handler."""
        _LOGGER.debug(f"{call.service} service called")
        if call.service == SERVICE_MOVE:
            await async_virtual_move_service(hass, call)

    # Build up services...
    if not hasattr(hass.data[COMPONENT_SERVICES], PLATFORM_DOMAIN):
        _LOGGER.debug("installing handlers")
        hass.data[COMPONENT_SERVICES][PLATFORM_DOMAIN] = "installed"
        hass.services.async_register(
            COMPONENT_DOMAIN,
            SERVICE_MOVE,
            async_virtual_service,
            schema=SERVICE_SCHEMA,
        )


class VirtualDeviceTracker(TrackerEntity, VirtualEntity):
    """Represent a tracked device."""

    def __init__(self, config):
        """Initialize a Virtual Device Tracker."""

        # Handle deprecated option.
        if config.get(CONF_LOCATION, None) is not None:
            _LOGGER.info(
                "'location' option is deprecated for virtual device trackers, please use 'initial_value'"
            )
            config[CONF_INITIAL_VALUE] = config.pop(CONF_LOCATION)

        super().__init__(config, PLATFORM_DOMAIN)

        self._location = None

        _LOGGER.debug(f"{self._attr_name}, available={self._attr_available}")
        _LOGGER.debug(f"{self._attr_name}, entity={self.entity_id}")

    def _create_state(self, config):
        _LOGGER.debug(f"device_tracker-create=config={config}")
        super()._create_state(config)
        self._location = config.get(CONF_INITIAL_VALUE)

    def _restore_state(self, state, config):
        _LOGGER.debug(f"device_tracker-restore=state={state.state}")
        _LOGGER.debug(f"device_tracker-restore=attrs={state.attributes}")
        if ATTR_AVAILABLE not in state.attributes:
            _LOGGER.debug("looks wrong, from upgrade? creating instead...")
            self._create_state(config)
        else:
            super()._restore_state(state, config)
            self._location = state.state

    @property
    def location_name(self) -> str | None:
        """Return a location name for the current location of the device."""
        return self._location

    @property
    def source_type(self) -> SourceType | str:
        return "virtual"

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return None

    def move(self, new_location):
        _LOGGER.debug(f"{self._attr_name} moving to {new_location}")
        self._location = new_location
        self.async_schedule_update_ha_state()


async def async_virtual_move_service(hass, call):
    for entity_id in call.data["entity_id"]:
        _LOGGER.debug(f"moving {entity_id}")
        get_entity_from_domain(hass, PLATFORM_DOMAIN, entity_id).move(
            call.data[CONF_LOCATION]
        )
