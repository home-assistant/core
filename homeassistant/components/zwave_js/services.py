"""Methods and classes related to executing Z-Wave commands and publishing these to hass."""
import logging
from typing import Optional, cast

import voluptuous as vol
from zwave_js_server.const import CommandClass
from zwave_js_server.model.node import Node as ZwaveNode, get_value_id

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import const
from .entity import get_home_and_node_id_from_device_id

_LOGGER = logging.getLogger(__name__)


class ZWaveServices:
    """Class that holds our services (Zwave Commands) that should be published to hass."""

    def __init__(
        self, hass: HomeAssistant, dev_reg: DeviceRegistry, ent_reg: EntityRegistry
    ):
        """Initialize with hass, device registry, and entity registry objects."""
        self._hass = hass
        self._dev_reg = dev_reg
        self._ent_reg = ent_reg

    @callback
    def async_register(self) -> None:
        """Register all our services."""
        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_SET_CONFIG_VALUE,
            self.async_set_config_value,
            schema=vol.All(
                {
                    vol.Exclusive(ATTR_DEVICE_ID, "id"): cv.string,
                    vol.Exclusive(ATTR_ENTITY_ID, "id"): cv.string,
                    vol.Optional(const.ATTR_ENDPOINT): vol.Coerce(int),
                    vol.Required(const.ATTR_CONFIG_PROPERTY): vol.Coerce(int),
                    vol.Optional(const.ATTR_CONFIG_PROPERTY_KEY_NAME): cv.string,
                    vol.Required(const.ATTR_CONFIG_VALUE): vol.Coerce(int),
                },
                cv.has_at_least_one_key(ATTR_DEVICE_ID, ATTR_ENTITY_ID),
            ),
        )

    @callback
    def async_get_node_from_device_id(self, device_id: Optional[str]) -> ZwaveNode:
        """Get node from a device ID."""
        if not device_id:
            return None

        device_entry = self._dev_reg.async_get(device_id)

        if not device_entry:
            raise ValueError("Device ID is not valid")

        # Use device config entry ID's to validate that this is a valid zwave_js device
        # and to get the client
        config_entry_ids = device_entry.config_entries
        config_entry_id = next(
            (
                config_entry_id
                for config_entry_id in config_entry_ids
                if cast(
                    ConfigEntry,
                    self._hass.config_entries.async_get_entry(config_entry_id),
                ).domain
                == const.DOMAIN
            ),
            None,
        )
        if (
            config_entry_id is None
            or config_entry_id not in self._hass.data[const.DOMAIN]
        ):
            raise ValueError("Device is not from an existing zwave_js config entry")

        client = self._hass.data[const.DOMAIN][config_entry_id][const.DATA_CLIENT]

        # Get node ID from device identifier, perform some validation, and then get the
        # node
        identifier = next(
            (
                get_home_and_node_id_from_device_id(identifier)
                for identifier in device_entry.identifiers
                if identifier[0] == const.DOMAIN
            ),
            None,
        )

        if identifier is None or identifier[1] not in client.driver.controller.nodes:
            raise ValueError("Device node can't be found")

        return client.driver.controller.nodes[identifier[1]]

    @callback
    def async_get_node_from_entity_id(self, entity_id: Optional[str]) -> ZwaveNode:
        """Get node from an entity ID."""
        if not entity_id:
            return None

        entity_entry = self._ent_reg.async_get(entity_id)

        if not entity_entry:
            raise ValueError("Entity ID is not valid")

        if entity_entry.platform != const.DOMAIN:
            raise ValueError("Entity is not from zwave_js integration")

        return self.async_get_node_from_device_id(entity_entry.device_id)

    async def async_set_config_value(self, service: ServiceCall) -> None:
        """Set a config value on a node."""
        node: ZwaveNode = self.async_get_node_from_entity_id(
            service.data.get(ATTR_ENTITY_ID)
        ) or self.async_get_node_from_device_id(service.data.get(ATTR_DEVICE_ID))
        property = service.data[const.ATTR_CONFIG_PROPERTY]
        property_key_name = service.data.get(const.ATTR_CONFIG_PROPERTY_KEY_NAME)
        endpoint = service.data.get(const.ATTR_ENDPOINT)
        selection = service.data[const.ATTR_CONFIG_VALUE]

        value_id = get_value_id(
            node,
            {
                "commandClass": CommandClass.CONFIGURATION,
                "property": property,
                "propertyKeyName": property_key_name,
                "endpoint": endpoint,
            },
        )
        config_values = node.get_configuration_values()
        value_error = (
            f"(property: {property}, property_key_name: {property_key_name}, "
            f"endpoint: {endpoint}, value_id: {value_id})"
        )

        try:
            await node.async_set_value(config_values[value_id], selection)
        except KeyError:
            raise ValueError(f"Configuration Value could not be found {value_error}")

        _LOGGER.info(
            (
                "Setting configuration value for (property: %s, property key name: %s, "
                "endpoint: %s, value_id: %s) on Node %s with value %s"
            ),
            property,
            property_key_name,
            endpoint,
            value_id,
            node,
            selection,
        )
