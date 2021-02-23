"""Methods and classes related to executing Z-Wave commands and publishing these to hass."""

import logging
from typing import Dict, Set, Union

import voluptuous as vol
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.util.node import async_set_config_parameter

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import EntityRegistry

from . import const
from .helpers import async_get_node_from_device_id, async_get_node_from_entity_id

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

    def __init__(self, hass: HomeAssistant, ent_reg: EntityRegistry):
        """Initialize with hass object."""
        self._hass = hass
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
                    vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
                    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
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

        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_REFRESH_VALUE,
            self.async_poll_value,
            schema=vol.Schema(
                {
                    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
                    vol.Optional(const.ATTR_REFRESH_ALL_VALUES, default=False): bool,
                }
            ),
        )

    async def async_set_config_parameter(self, service: ServiceCall) -> None:
        """Set a config value on a node."""
        nodes: Set[ZwaveNode] = set()
        if ATTR_ENTITY_ID in service.data:
            nodes |= {
                async_get_node_from_entity_id(self._hass, entity_id)
                for entity_id in service.data[ATTR_ENTITY_ID]
            }
        if ATTR_DEVICE_ID in service.data:
            nodes |= {
                async_get_node_from_device_id(self._hass, device_id)
                for device_id in service.data[ATTR_DEVICE_ID]
            }
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
                _LOGGER.info(
                    "Set configuration parameter %s on Node %s with value %s",
                    zwave_value,
                    node,
                    new_value,
                )
            else:
                raise ValueError(
                    f"Unable to set configuration parameter on Node {node} with "
                    f"value {new_value}"
                )

    async def async_poll_value(self, service: ServiceCall) -> None:
        """Poll value on a node."""
        for entity_id in service.data[ATTR_ENTITY_ID]:
            entry = self._ent_reg.async_get(entity_id)
            if entry is None or entry.platform != const.DOMAIN:
                raise ValueError(
                    f"Entity {entity_id} is not a valid {const.DOMAIN} entity."
                )
            async_dispatcher_send(
                self._hass,
                f"{const.DOMAIN}_{entry.unique_id}_poll_value",
                service.data[const.ATTR_REFRESH_ALL_VALUES],
            )
