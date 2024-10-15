"""Common opentherm_gw entity properties."""

import logging

import pyotgw.vars as gw_vars

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription

from . import OpenThermGatewayHub
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

TRANSLATE_SOURCE = {
    gw_vars.BOILER: "Boiler",
    gw_vars.OTGW: None,
    gw_vars.THERMOSTAT: "Thermostat",
}


class OpenThermEntityDescription(EntityDescription):
    """Describe common opentherm_gw entity properties."""

    friendly_name_format: str


class OpenThermEntity(Entity):
    """Represent an OpenTherm Gateway entity."""

    _attr_should_poll = False
    _attr_entity_registry_enabled_default = False
    _attr_available = False
    entity_description: OpenThermEntityDescription

    def __init__(
        self,
        gw_hub: OpenThermGatewayHub,
        source: str,
        description: OpenThermEntityDescription,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        self._gateway = gw_hub
        self._source = source
        friendly_name_format = (
            f"{description.friendly_name_format} ({TRANSLATE_SOURCE[source]})"
            if TRANSLATE_SOURCE[source] is not None
            else description.friendly_name_format
        )
        self._attr_name = friendly_name_format.format(gw_hub.name)
        self._attr_unique_id = f"{gw_hub.hub_id}-{source}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, gw_hub.hub_id)},
            manufacturer="Schelte Bron",
            model="OpenTherm Gateway",
            name=gw_hub.name,
            sw_version=gw_hub.gw_version,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates from the component."""
        _LOGGER.debug("Added OpenTherm Gateway entity %s", self._attr_name)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._gateway.update_signal, self.receive_report
            )
        )

    @callback
    def receive_report(self, status: dict[str, dict]) -> None:
        """Handle status updates from the component."""
        # Must be implemented at the platform level.
        raise NotImplementedError
