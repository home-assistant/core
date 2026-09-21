"""Support for OpenTherm Gateway number entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenThermGatewayHub
from .const import DATA_GATEWAYS, DATA_OPENTHERM_GW, GATEWAY_DEVICE_DESCRIPTION
from .entity import OpenThermEntity, OpenThermEntityDescription


@dataclass(frozen=True, kw_only=True)
class OpenThermNumberEntityDescription(
    OpenThermEntityDescription, NumberEntityDescription
):
    """Describes an opentherm_gw number entity."""

    set_action: Callable[[OpenThermGatewayHub, float], Awaitable]


NUMBER_DESCRIPTIONS: tuple[OpenThermNumberEntityDescription, ...] = (
    OpenThermNumberEntityDescription(
        key="control_setpoint_override",
        translation_key="control_setpoint_override_n",
        translation_placeholders={"circuit_number": "1"},
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_max_value=100,
        native_min_value=0,
        native_step=0.1,
        device_description=GATEWAY_DEVICE_DESCRIPTION,
        set_action=lambda hub, value: hub.gateway.set_control_setpoint(value),
    ),
    OpenThermNumberEntityDescription(
        key="control_setpoint_override_2",
        translation_key="control_setpoint_override_n",
        translation_placeholders={"circuit_number": "2"},
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_max_value=100,
        native_min_value=0,
        native_step=0.1,
        device_description=GATEWAY_DEVICE_DESCRIPTION,
        set_action=lambda hub, value: hub.gateway.set_control_setpoint_2(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OpenTherm Gateway number entities."""
    gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]]

    async_add_entities(
        OpenThermNumber(gw_hub, description) for description in NUMBER_DESCRIPTIONS
    )


class OpenThermNumber(OpenThermEntity, NumberEntity):
    """Represent an OpenTherm Gateway number."""

    entity_description: OpenThermNumberEntityDescription

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        new_value = await self.entity_description.set_action(self._gateway, value)
        self._attr_native_value = None if new_value in [0, None] else float(new_value)
        self.async_write_ha_state()
