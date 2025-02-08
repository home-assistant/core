"""Common opentherm_gw entity properties."""

import logging

import pyotgw.vars as gw_vars

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription

from . import OpenThermGatewayHub
from .const import DOMAIN, OpenThermDataSource, OpenThermDeviceDescription

_LOGGER = logging.getLogger(__name__)

TRANSLATE_SOURCE = {
    gw_vars.BOILER: "Boiler",
    gw_vars.OTGW: None,
    gw_vars.THERMOSTAT: "Thermostat",
}


class OpenThermEntityDescription(EntityDescription):
    """Describe common opentherm_gw entity properties."""

    device_description: OpenThermDeviceDescription


class OpenThermEntity(Entity):
    """Represent an OpenTherm entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: OpenThermEntityDescription

    def __init__(
        self,
        gw_hub: OpenThermGatewayHub,
        description: OpenThermEntityDescription,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        self._gateway = gw_hub
        self._attr_unique_id = f"{gw_hub.hub_id}-{description.device_description.device_identifier}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{gw_hub.hub_id}-{description.device_description.device_identifier}",
                )
            },
        )

    @property
    def available(self) -> bool:
        """Return connection status of the hub to indicate availability."""
        return self._gateway.connected


class OpenThermStatusEntity(OpenThermEntity):
    """Represent an OpenTherm entity that receives status updates."""

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates from the component."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._gateway.update_signal, self.receive_report
            )
        )

    @callback
    def receive_report(self, status: dict[OpenThermDataSource, dict]) -> None:
        """Handle status updates from the component."""
        # Must be implemented at the platform level.
        raise NotImplementedError
