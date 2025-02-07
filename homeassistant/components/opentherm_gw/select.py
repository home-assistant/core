"""Support for OpenTherm Gateway select entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from functools import partial

from pyotgw.vars import (
    OTGW_GPIO_A,
    OTGW_GPIO_B,
    OTGW_LED_A,
    OTGW_LED_B,
    OTGW_LED_C,
    OTGW_LED_D,
    OTGW_LED_E,
    OTGW_LED_F,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
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
from .entity import OpenThermEntityDescription, OpenThermStatusEntity


class OpenThermSelectGPIOMode(StrEnum):
    """OpenTherm Gateway GPIO modes."""

    INPUT = "input"
    GROUND = "ground"
    VCC = "vcc"
    LED_E = "led_e"
    LED_F = "led_f"
    HOME = "home"
    AWAY = "away"
    DS1820 = "ds1820"
    DHW_BLOCK = "dhw_block"


class OpenThermSelectLEDMode(StrEnum):
    """OpenThermGateway LED modes."""

    RX_ANY = "receive_any"
    TX_ANY = "transmit_any"
    THERMOSTAT_TRAFFIC = "thermostat_traffic"
    BOILER_TRAFFIC = "boiler_traffic"
    SETPOINT_OVERRIDE_ACTIVE = "setpoint_override_active"
    FLAME_ON = "flame_on"
    CENTRAL_HEATING_ON = "central_heating_on"
    HOT_WATER_ON = "hot_water_on"
    COMFORT_MODE_ON = "comfort_mode_on"
    TX_ERROR_DETECTED = "transmit_error_detected"
    BOILER_MAINTENANCE_REQUIRED = "boiler_maintenance_required"
    RAISED_POWER_MODE_ACTIVE = "raised_power_mode_active"


class PyotgwGPIOMode(IntEnum):
    """pyotgw GPIO modes."""

    INPUT = 0
    GROUND = 1
    VCC = 2
    LED_E = 3
    LED_F = 4
    HOME = 5
    AWAY = 6
    DS1820 = 7
    DHW_BLOCK = 8


class PyotgwLEDMode(StrEnum):
    """pyotgw LED modes."""

    RX_ANY = "R"
    TX_ANY = "X"
    THERMOSTAT_TRAFFIC = "T"
    BOILER_TRAFFIC = "B"
    SETPOINT_OVERRIDE_ACTIVE = "O"
    FLAME_ON = "F"
    CENTRAL_HEATING_ON = "H"
    HOT_WATER_ON = "W"
    COMFORT_MODE_ON = "C"
    TX_ERROR_DETECTED = "E"
    BOILER_MAINTENANCE_REQUIRED = "M"
    RAISED_POWER_MODE_ACTIVE = "P"


def pyotgw_led_mode_to_ha_led_mode(
    pyotgw_led_mode: PyotgwLEDMode,
) -> OpenThermSelectLEDMode | None:
    """Convert pyotgw LED mode to Home Assistant LED mode."""
    return (
        OpenThermSelectLEDMode[PyotgwLEDMode(pyotgw_led_mode).name]
        if pyotgw_led_mode in PyotgwLEDMode
        else None
    )


async def set_gpio_mode(
    gpio_id: str, gw_hub: OpenThermGatewayHub, mode: str
) -> OpenThermSelectGPIOMode | None:
    """Set gpio mode, return selected option or None."""
    value = await gw_hub.gateway.set_gpio_mode(
        gpio_id, PyotgwGPIOMode[OpenThermSelectGPIOMode(mode).name]
    )
    return (
        OpenThermSelectGPIOMode[PyotgwGPIOMode(value).name]
        if value in PyotgwGPIOMode
        else None
    )


async def set_led_mode(
    led_id: str, gw_hub: OpenThermGatewayHub, mode: str
) -> OpenThermSelectLEDMode | None:
    """Set gpio mode, return selected option or None."""
    value = await gw_hub.gateway.set_led_mode(
        led_id, PyotgwLEDMode[OpenThermSelectLEDMode(mode).name]
    )
    return (
        OpenThermSelectLEDMode[PyotgwLEDMode(value).name]
        if value in PyotgwLEDMode
        else None
    )


@dataclass(frozen=True, kw_only=True)
class OpenThermSelectEntityDescription(
    OpenThermEntityDescription, SelectEntityDescription
):
    """Describes an opentherm_gw select entity."""

    select_action: Callable[[OpenThermGatewayHub, str], Awaitable]
    convert_pyotgw_state_to_ha_state: Callable


SELECT_DESCRIPTIONS: tuple[OpenThermSelectEntityDescription, ...] = (
    OpenThermSelectEntityDescription(
        key=OTGW_GPIO_A,
        translation_key="gpio_mode_n",
        translation_placeholders={"gpio_id": "A"},
        device_description=GATEWAY_DEVICE_DESCRIPTION,
        options=[
            mode
            for mode in OpenThermSelectGPIOMode
            if mode != OpenThermSelectGPIOMode.DS1820
        ],
        select_action=partial(set_gpio_mode, "A"),
        convert_pyotgw_state_to_ha_state=(
            lambda state: OpenThermSelectGPIOMode[PyotgwGPIOMode(state).name]
            if state in PyotgwGPIOMode
            else None
        ),
    ),
    OpenThermSelectEntityDescription(
        key=OTGW_GPIO_B,
        translation_key="gpio_mode_n",
        translation_placeholders={"gpio_id": "B"},
        device_description=GATEWAY_DEVICE_DESCRIPTION,
        options=list(OpenThermSelectGPIOMode),
        select_action=partial(set_gpio_mode, "B"),
        convert_pyotgw_state_to_ha_state=(
            lambda state: OpenThermSelectGPIOMode[PyotgwGPIOMode(state).name]
            if state in PyotgwGPIOMode
            else None
        ),
    ),
    OpenThermSelectEntityDescription(
        key=OTGW_LED_A,
        translation_key="led_mode_n",
        translation_placeholders={"led_id": "A"},
        device_description=GATEWAY_DEVICE_DESCRIPTION,
        options=list(OpenThermSelectLEDMode),
        select_action=partial(set_led_mode, "A"),
        convert_pyotgw_state_to_ha_state=pyotgw_led_mode_to_ha_led_mode,
    ),
    OpenThermSelectEntityDescription(
        key=OTGW_LED_B,
        translation_key="led_mode_n",
        translation_placeholders={"led_id": "B"},
        device_description=GATEWAY_DEVICE_DESCRIPTION,
        options=list(OpenThermSelectLEDMode),
        select_action=partial(set_led_mode, "B"),
        convert_pyotgw_state_to_ha_state=pyotgw_led_mode_to_ha_led_mode,
    ),
    OpenThermSelectEntityDescription(
        key=OTGW_LED_C,
        translation_key="led_mode_n",
        translation_placeholders={"led_id": "C"},
        device_description=GATEWAY_DEVICE_DESCRIPTION,
        options=list(OpenThermSelectLEDMode),
        select_action=partial(set_led_mode, "C"),
        convert_pyotgw_state_to_ha_state=pyotgw_led_mode_to_ha_led_mode,
    ),
    OpenThermSelectEntityDescription(
        key=OTGW_LED_D,
        translation_key="led_mode_n",
        translation_placeholders={"led_id": "D"},
        device_description=GATEWAY_DEVICE_DESCRIPTION,
        options=list(OpenThermSelectLEDMode),
        select_action=partial(set_led_mode, "D"),
        convert_pyotgw_state_to_ha_state=pyotgw_led_mode_to_ha_led_mode,
    ),
    OpenThermSelectEntityDescription(
        key=OTGW_LED_E,
        translation_key="led_mode_n",
        translation_placeholders={"led_id": "E"},
        device_description=GATEWAY_DEVICE_DESCRIPTION,
        options=list(OpenThermSelectLEDMode),
        select_action=partial(set_led_mode, "E"),
        convert_pyotgw_state_to_ha_state=pyotgw_led_mode_to_ha_led_mode,
    ),
    OpenThermSelectEntityDescription(
        key=OTGW_LED_F,
        translation_key="led_mode_n",
        translation_placeholders={"led_id": "F"},
        device_description=GATEWAY_DEVICE_DESCRIPTION,
        options=list(OpenThermSelectLEDMode),
        select_action=partial(set_led_mode, "F"),
        convert_pyotgw_state_to_ha_state=pyotgw_led_mode_to_ha_led_mode,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OpenTherm Gateway select entities."""
    gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]]

    async_add_entities(
        OpenThermSelect(gw_hub, description) for description in SELECT_DESCRIPTIONS
    )


class OpenThermSelect(OpenThermStatusEntity, SelectEntity):
    """Represent an OpenTherm Gateway select."""

    _attr_current_option = None
    _attr_entity_category = EntityCategory.CONFIG
    entity_description: OpenThermSelectEntityDescription

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        new_option = await self.entity_description.select_action(self._gateway, option)
        if new_option is not None:
            self._attr_current_option = new_option
            self.async_write_ha_state()

    @callback
    def receive_report(self, status: dict[OpenThermDataSource, dict]) -> None:
        """Handle status updates from the component."""
        state = status[self.entity_description.device_description.data_source].get(
            self.entity_description.key
        )
        self._attr_current_option = (
            self.entity_description.convert_pyotgw_state_to_ha_state(state)
        )
        self.async_write_ha_state()
