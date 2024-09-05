"""Support for OpenTherm Gateway switches."""

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
    GATEWAY_DEVICE_DESCRIPTION,
    OpenThermDataSource,
)
from .entity import OpenThermEntity, OpenThermEntityDescription


@dataclass(frozen=True, kw_only=True)
class OpenThermSwitchEntityDescription(
    OpenThermEntityDescription, SwitchEntityDescription
):
    """Describes opentherm_gw switch entity."""


SWITCH_DESCRIPTIONS: tuple[OpenThermSwitchEntityDescription, ...] = (
    OpenThermSwitchEntityDescription(
        key="central_heating_1_override",
        translation_key="central_heating_override_n",
        translation_placeholders={"circuit_number": "1"},
        device_description=GATEWAY_DEVICE_DESCRIPTION,
        entity_registry_enabled_default=False,
    ),
    OpenThermSwitchEntityDescription(
        key="central_heating_1_override",
        translation_key="central_heating_override_n",
        translation_placeholders={"circuit_number": "2"},
        device_description=GATEWAY_DEVICE_DESCRIPTION,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OpenTherm Gateway switches."""
    gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]]

    async_add_entities(
        OpenThermSwitch(gw_hub, description) for description in SWITCH_DESCRIPTIONS
    )


class OpenThermSwitch(OpenThermEntity, SwitchEntity):
    """Represent an OpenTherm Gateway switch."""

    _attr_entity_category = EntityCategory.CONFIG
    entity_description: OpenThermSwitchEntityDescription

    @callback
    def receive_report(self, status: dict[OpenThermDataSource, dict]) -> None:
        """Handle status updates from the component."""
        # We don't need
