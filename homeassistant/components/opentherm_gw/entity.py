"""Common opentherm_gw entity properties."""

import logging

import pyotgw.vars as gw_vars

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription

from . import OpenThermGatewayHub
from .const import (
    DEVICE_IDENT_BOILER,
    DEVICE_IDENT_GATEWAY,
    DEVICE_IDENT_THERMOSTAT,
    DOMAIN,
    OpenThermDataSource,
)

_LOGGER = logging.getLogger(__name__)

TRANSLATE_SOURCE = {
    gw_vars.BOILER: "Boiler",
    gw_vars.OTGW: None,
    gw_vars.THERMOSTAT: "Thermostat",
}


class OpenThermEntityDescription(EntityDescription):
    """Describe common opentherm_gw entity properties."""


class OpenThermBaseEntity(Entity):
    """Represent an OpenTherm entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _data_source: OpenThermDataSource
    entity_description: OpenThermEntityDescription

    def __init__(
        self,
        gw_hub: OpenThermGatewayHub,
        description: OpenThermEntityDescription,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        self._gateway = gw_hub

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates from the component."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._gateway.update_signal, self.receive_report
            )
        )

    @property
    def available(self) -> bool:
        """Return connection status of the hub to indicate availability."""
        return self._gateway.connected

    @callback
    def receive_report(self, status: dict[str, dict]) -> None:
        """Handle status updates from the component."""
        # Must be implemented at the platform level.
        raise NotImplementedError


class OpenThermBoilerDeviceEntity(OpenThermBaseEntity):
    """Represent an OpenTherm Boiler entity."""

    _data_source = OpenThermDataSource.BOILER

    def __init__(
        self,
        gw_hub: OpenThermGatewayHub,
        description: OpenThermEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(gw_hub, description)
        self._attr_unique_id = (
            f"{gw_hub.hub_id}-{DEVICE_IDENT_BOILER}-{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{gw_hub.hub_id}-{DEVICE_IDENT_BOILER}")},
        )


class OpenThermGatewayDeviceEntity(OpenThermBaseEntity):
    """Represent an OpenTherm Gateway entity."""

    _data_source = OpenThermDataSource.GATEWAY

    def __init__(
        self,
        gw_hub: OpenThermGatewayHub,
        description: OpenThermEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(gw_hub, description)
        self._attr_unique_id = (
            f"{gw_hub.hub_id}-{DEVICE_IDENT_GATEWAY}-{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{gw_hub.hub_id}-{DEVICE_IDENT_GATEWAY}")},
        )


class OpenThermThermostatDeviceEntity(OpenThermBaseEntity):
    """Represent an OpenTherm Thermostat entity."""

    _data_source = OpenThermDataSource.THERMOSTAT

    def __init__(
        self,
        gw_hub: OpenThermGatewayHub,
        description: OpenThermEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(gw_hub, description)
        self._attr_unique_id = (
            f"{gw_hub.hub_id}-{DEVICE_IDENT_THERMOSTAT}-{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{gw_hub.hub_id}-{DEVICE_IDENT_THERMOSTAT}")},
        )
