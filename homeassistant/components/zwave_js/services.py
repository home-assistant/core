"""Methods and classes related to executing Z-Wave commands and publishing these to hass."""
import logging
from typing import Dict, List, Union, cast

import voluptuous as vol
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.util.node import async_set_config_parameter

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import const
from .entity import get_home_and_node_id_from_device_id

_LOGGER = logging.getLogger(__name__)


def parameter_name_does_not_need_bitmask(
    val: Dict[str, Union[int, str]]
) -> Dict[str, Union[int, str]]:
    """Validate that if a parameter name is provided, bitmask is not as well."""
    if isinstance(val[const.ATTR_CONFIG_PARAMETER], str) and (
        val.get(const.ATTR_CONFIG_PARAMETER_BITMASK)
    ):
        raise vol.Invalid(
            "Don't include a bitmask when a parameter name is specified",
            path=[const.ATTR_CONFIG_PARAMETER, const.ATTR_CONFIG_PARAMETER_BITMASK],
        )
    return val


# Validates that a bitmask is provided in hex form and converts it to decimal
# int equivalent since that's what the library uses
BITMASK_SCHEMA = vol.All(
    cv.string, vol.Lower, vol.Match(r"^(0x)?[0-9a-f]+$"), lambda value: int(value, 16)
)


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
            const.SERVICE_SET_CONFIG_PARAMETER,
            self.async_set_config_parameter,
            schema=vol.All(
                {
                    vol.Exclusive(ATTR_DEVICE_ID, "id"): cv.string,
                    vol.Exclusive(ATTR_ENTITY_ID, "id"): cv.entity_ids,
                    vol.Required(const.ATTR_CONFIG_PARAMETER): vol.Any(
                        vol.Coerce(int), cv.string
                    ),
                    vol.Optional(const.ATTR_CONFIG_PARAMETER_BITMASK): vol.Any(
                        vol.Coerce(int), BITMASK_SCHEMA
                    ),
                    vol.Required(const.ATTR_CONFIG_VALUE): vol.Any(
                        vol.Coerce(int), cv.string
                    ),
                },
                cv.has_at_least_one_key(ATTR_DEVICE_ID, ATTR_ENTITY_ID),
                parameter_name_does_not_need_bitmask,
            ),
        )

    @callback
    def async_get_node_from_device_id(self, device_id: str) -> ZwaveNode:
        """Get node from a device ID."""
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

        node_id = int(identifier[1]) if identifier is not None else None

        if node_id is None or node_id not in client.driver.controller.nodes:
            raise ValueError("Device node can't be found")

        return client.driver.controller.nodes[node_id]

    @callback
    def async_get_node_from_entity_id(self, entity_id: str) -> ZwaveNode:
        """Get node from an entity ID."""
        entity_entry = self._ent_reg.async_get(entity_id)

        if not entity_entry:
            raise ValueError("Entity ID is not valid")

        if entity_entry.platform != const.DOMAIN:
            raise ValueError("Entity is not from zwave_js integration")

        # Assert for mypy, safe because we know that zwave_js entities are always
        # tied to a device
        assert entity_entry.device_id
        return self.async_get_node_from_device_id(entity_entry.device_id)

    async def async_set_config_parameter(self, service: ServiceCall) -> None:
        """Set a config value on a node."""
        nodes: List[ZwaveNode]
        if ATTR_ENTITY_ID in service.data:
            nodes = [
                self.async_get_node_from_entity_id(entity_id)
                for entity_id in service.data[ATTR_ENTITY_ID]
            ]
        else:
            nodes = [self.async_get_node_from_device_id(service.data[ATTR_DEVICE_ID])]

        property_or_property_name = service.data[const.ATTR_CONFIG_PARAMETER]
        property_key = service.data.get(const.ATTR_CONFIG_PARAMETER_BITMASK)
        new_value = service.data[const.ATTR_CONFIG_VALUE]

        for node in nodes:
            zwave_value = await async_set_config_parameter(
                node,
                new_value,
                property_or_property_name,
                property_key=property_key,
            )

            if zwave_value:
                error_msg = "Set configuration parameter %s on Node %s with value %s"
            else:
                error_msg = (
                    "Unable to set configuration parameter on Node %s with value %s"
                )

            _LOGGER.info(error_msg, zwave_value, node, new_value)
