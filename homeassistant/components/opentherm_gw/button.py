"""Support for OpenTherm Gateway buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import pyotgw.vars as gw_vars

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OpenThermGatewayHub
from .const import (
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
    GATEWAY_DEVICE_DESCRIPTION,
    OpenThermDataSource,
)
from .entity import OpenThermEntity, OpenThermEntityDescription


@dataclass(frozen=True, kw_only=True)
class OpenThermButtonEntityDescription(
    ButtonEntityDescription, OpenThermEntityDescription
):
    """Describes an opentherm_gw button entity."""

    action: Callable[[OpenThermGatewayHub], Awaitable]


BUTTON_DESCRIPTIONS: tuple[OpenThermButtonEntityDescription, ...] = (
    OpenThermButtonEntityDescription(
        key="restart_button",
        device_class=ButtonDeviceClass.RESTART,
        device_description=GATEWAY_DEVICE_DESCRIPTION,
        action=lambda hub: hub.gateway.set_mode(gw_vars.OTGW_MODE_RESET),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OpenTherm Gateway buttons."""
    gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]]

    async_add_entities(
        OpenThermButton(gw_hub, description) for description in BUTTON_DESCRIPTIONS
    )


class OpenThermButton(OpenThermEntity, ButtonEntity):
    """Representation of an OpenTherm button."""

    _attr_entity_category = EntityCategory.CONFIG
    entity_description: OpenThermButtonEntityDescription

    @callback
    def receive_report(self, status: dict[OpenThermDataSource, dict]) -> None:
        """Handle status updates from the component."""
        # We don't need any information from the reports here

    async def async_press(self) -> None:
        """Perform button action."""
        await self.entity_description.action(self._gateway)
