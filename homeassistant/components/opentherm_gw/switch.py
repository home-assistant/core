"""Support for OpenTherm Gateway switches."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenThermGatewayHub
from .const import DATA_GATEWAYS, DATA_OPENTHERM_GW, GATEWAY_DEVICE_DESCRIPTION
from .entity import OpenThermEntity, OpenThermEntityDescription


@dataclass(frozen=True, kw_only=True)
class OpenThermSwitchEntityDescription(
    OpenThermEntityDescription, SwitchEntityDescription
):
    """Describes an opentherm_gw switch entity."""

    turn_off_action: Callable[[OpenThermGatewayHub], Awaitable[int | None]]
    turn_on_action: Callable[[OpenThermGatewayHub], Awaitable[int | None]]


SWITCH_DESCRIPTIONS: tuple[OpenThermSwitchEntityDescription, ...] = (
    OpenThermSwitchEntityDescription(
        key="central_heating_1_override",
        translation_key="central_heating_override_n",
        translation_placeholders={"circuit_number": "1"},
        device_description=GATEWAY_DEVICE_DESCRIPTION,
        turn_off_action=lambda hub: hub.gateway.set_ch_enable_bit(0),
        turn_on_action=lambda hub: hub.gateway.set_ch_enable_bit(1),
    ),
    OpenThermSwitchEntityDescription(
        key="central_heating_2_override",
        translation_key="central_heating_override_n",
        translation_placeholders={"circuit_number": "2"},
        device_description=GATEWAY_DEVICE_DESCRIPTION,
        turn_off_action=lambda hub: hub.gateway.set_ch2_enable_bit(0),
        turn_on_action=lambda hub: hub.gateway.set_ch2_enable_bit(1),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OpenTherm Gateway switches."""
    gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]]

    async_add_entities(
        OpenThermSwitch(gw_hub, description) for description in SWITCH_DESCRIPTIONS
    )


class OpenThermSwitch(OpenThermEntity, SwitchEntity):
    """Represent an OpenTherm Gateway switch."""

    _attr_assumed_state = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    entity_description: OpenThermSwitchEntityDescription

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        value = await self.entity_description.turn_off_action(self._gateway)
        self._attr_is_on = bool(value) if value is not None else None
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        value = await self.entity_description.turn_on_action(self._gateway)
        self._attr_is_on = bool(value) if value is not None else None
        self.async_write_ha_state()
