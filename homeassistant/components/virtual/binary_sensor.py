"""Provide support for a virtual binary sensor."""

import logging
from typing import cast

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DOMAIN as PLATFORM_DOMAIN,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import get_entity_configs, get_entity_from_domain
from .const import (
    ATTR_GROUP_NAME,
    COMPONENT_DOMAIN,
    COMPONENT_NETWORK,
    COMPONENT_SERVICES,
    CONF_CLASS,
    CONF_COORDINATED,
    CONF_INITIAL_VALUE,
    CONF_SIMULATE_NETWORK,
)
from .coordinator import VirtualDataUpdateCoordinator
from .entity import CoordinatedVirtualEntity, VirtualEntity, virtual_schema
from .network import NetworkProxy

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = [COMPONENT_DOMAIN]

DEFAULT_BINARY_SENSOR_VALUE = "off"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    virtual_schema(
        DEFAULT_BINARY_SENSOR_VALUE,
        {
            vol.Optional(CONF_CLASS): cv.string,
        },
    )
)
BINARY_SENSOR_SCHEMA = vol.Schema(
    virtual_schema(
        DEFAULT_BINARY_SENSOR_VALUE,
        {
            vol.Optional(CONF_CLASS): cv.string,
        },
    )
)

SERVICE_ON = "turn_on"
SERVICE_OFF = "turn_off"
SERVICE_TOGGLE = "toggle"
SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""

    coordinator: VirtualDataUpdateCoordinator = hass.data[COMPONENT_DOMAIN][
        entry.entry_id
    ]
    entities: list[VirtualBinarySensor] = []
    for entity_config in get_entity_configs(
        hass, entry.data[ATTR_GROUP_NAME], PLATFORM_DOMAIN
    ):
        entity_config = BINARY_SENSOR_SCHEMA(entity_config)
        if entity_config[CONF_COORDINATED]:
            entity = cast(
                VirtualBinarySensor,
                CoordinatedVirtualBinarySensor(entity_config, coordinator),
            )
        else:
            entity = VirtualBinarySensor(entity_config)

        if entity_config[CONF_SIMULATE_NETWORK]:
            entity = cast(VirtualBinarySensor, NetworkProxy(entity))
            hass.data[COMPONENT_NETWORK][entity.entity_id] = entity

        entities.append(entity)

    async_add_entities(entities)

    async def async_virtual_service(call):
        """Call virtual service handler."""
        if call.service == SERVICE_ON:
            await async_virtual_on_service(hass, call)
        if call.service == SERVICE_OFF:
            await async_virtual_off_service(hass, call)
        if call.service == SERVICE_TOGGLE:
            await async_virtual_toggle_service(hass, call)

    # Build up services...
    if not hasattr(hass.data[COMPONENT_SERVICES], PLATFORM_DOMAIN):
        hass.data[COMPONENT_SERVICES][PLATFORM_DOMAIN] = "installed"
        hass.services.async_register(
            COMPONENT_DOMAIN,
            SERVICE_ON,
            async_virtual_service,
            schema=SERVICE_SCHEMA,
        )
        hass.services.async_register(
            COMPONENT_DOMAIN,
            SERVICE_OFF,
            async_virtual_service,
            schema=SERVICE_SCHEMA,
        )
        hass.services.async_register(
            COMPONENT_DOMAIN,
            SERVICE_TOGGLE,
            async_virtual_service,
            schema=SERVICE_SCHEMA,
        )


class VirtualBinarySensor(VirtualEntity, BinarySensorEntity):
    """An implementation of a Virtual Binary Sensor."""

    def __init__(self, config):
        """Initialize a Virtual Binary Sensor."""
        super().__init__(config, PLATFORM_DOMAIN)

        self._attr_device_class = config.get(CONF_CLASS)

        _LOGGER.info("VirtualBinarySensor: %s created", self.name)

    def _create_state(self, config):
        super()._create_state(config)

        self._attr_is_on = config.get(CONF_INITIAL_VALUE).lower() == STATE_ON

    def _restore_state(self, state, config):
        super()._restore_state(state, config)

        self._attr_is_on = state.state.lower() == STATE_ON

    def _update_attributes(self):
        super()._update_attributes()
        self._attr_extra_state_attributes.update(
            {
                name: value
                for name, value in ((ATTR_DEVICE_CLASS, self._attr_device_class),)
                if value is not None
            }
        )

    def turn_on(self) -> None:
        """Turn on."""
        self._attr_is_on = True
        self.async_schedule_update_ha_state()

    def turn_off(self) -> None:
        """Turn off."""
        self._attr_is_on = False
        self.async_schedule_update_ha_state()

    def toggle(self) -> None:
        """Toggle."""
        if self.is_on:
            self.turn_off()
        else:
            self.turn_on()


async def async_virtual_on_service(hass, call):
    """Turn on service."""
    for entity_id in call.data["entity_id"]:
        get_entity_from_domain(hass, PLATFORM_DOMAIN, entity_id).turn_on()


async def async_virtual_off_service(hass, call):
    """Turn off service."""
    for entity_id in call.data["entity_id"]:
        get_entity_from_domain(hass, PLATFORM_DOMAIN, entity_id).turn_off()


async def async_virtual_toggle_service(hass, call):
    """Toggle service."""
    for entity_id in call.data["entity_id"]:
        get_entity_from_domain(hass, PLATFORM_DOMAIN, entity_id).toggle()


class CoordinatedVirtualBinarySensor(CoordinatedVirtualEntity, VirtualBinarySensor):
    """Representation of a Virtual switch."""

    def __init__(self, config, coordinator):
        """Initialize the Virtual switch device."""
        CoordinatedVirtualEntity.__init__(self, coordinator)
        VirtualBinarySensor.__init__(self, config)
