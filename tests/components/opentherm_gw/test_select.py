"""Test opentherm_gw select entities."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

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
import pytest

from homeassistant.components.opentherm_gw import DOMAIN as OPENTHERM_DOMAIN
from homeassistant.components.opentherm_gw.const import (
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
    OpenThermDeviceIdentifier,
)
from homeassistant.components.opentherm_gw.select import (
    OpenThermSelectGPIOMode,
    OpenThermSelectLEDMode,
    PyotgwGPIOMode,
    PyotgwLEDMode,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    (
        "entity_key",
        "target_func_name",
        "target_param_1",
        "target_param_2",
        "resulting_state",
    ),
    [
        (
            OTGW_GPIO_A,
            "set_gpio_mode",
            "A",
            PyotgwGPIOMode.VCC,
            OpenThermSelectGPIOMode.VCC,
        ),
        (
            OTGW_GPIO_B,
            "set_gpio_mode",
            "B",
            PyotgwGPIOMode.HOME,
            OpenThermSelectGPIOMode.HOME,
        ),
        (
            OTGW_LED_A,
            "set_led_mode",
            "A",
            PyotgwLEDMode.TX_ANY,
            OpenThermSelectLEDMode.TX_ANY,
        ),
        (
            OTGW_LED_B,
            "set_led_mode",
            "B",
            PyotgwLEDMode.RX_ANY,
            OpenThermSelectLEDMode.RX_ANY,
        ),
        (
            OTGW_LED_C,
            "set_led_mode",
            "C",
            PyotgwLEDMode.BOILER_TRAFFIC,
            OpenThermSelectLEDMode.BOILER_TRAFFIC,
        ),
        (
            OTGW_LED_D,
            "set_led_mode",
            "D",
            PyotgwLEDMode.THERMOSTAT_TRAFFIC,
            OpenThermSelectLEDMode.THERMOSTAT_TRAFFIC,
        ),
        (
            OTGW_LED_E,
            "set_led_mode",
            "E",
            PyotgwLEDMode.FLAME_ON,
            OpenThermSelectLEDMode.FLAME_ON,
        ),
        (
            OTGW_LED_F,
            "set_led_mode",
            "F",
            PyotgwLEDMode.BOILER_MAINTENANCE_REQUIRED,
            OpenThermSelectLEDMode.BOILER_MAINTENANCE_REQUIRED,
        ),
    ],
)
async def test_select_change_value(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_pyotgw: MagicMock,
    entity_key: str,
    target_func_name: str,
    target_param_1: str,
    target_param_2: str | int,
    resulting_state: str,
) -> None:
    """Test GPIO mode selector."""

    setattr(
        mock_pyotgw.return_value,
        target_func_name,
        AsyncMock(return_value=target_param_2),
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        select_entity_id := entity_registry.async_get_entity_id(
            SELECT_DOMAIN,
            OPENTHERM_DOMAIN,
            f"{mock_config_entry.data[CONF_ID]}-{OpenThermDeviceIdentifier.GATEWAY}-{entity_key}",
        )
    ) is not None
    assert hass.states.get(select_entity_id).state == STATE_UNKNOWN

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: select_entity_id, ATTR_OPTION: resulting_state},
        blocking=True,
    )
    assert hass.states.get(select_entity_id).state == resulting_state

    target = getattr(mock_pyotgw.return_value, target_func_name)
    target.assert_awaited_once_with(target_param_1, target_param_2)


@pytest.mark.parametrize(
    ("entity_key", "test_value", "resulting_state"),
    [
        (OTGW_GPIO_A, PyotgwGPIOMode.AWAY, OpenThermSelectGPIOMode.AWAY),
        (OTGW_GPIO_B, PyotgwGPIOMode.LED_F, OpenThermSelectGPIOMode.LED_F),
        (
            OTGW_LED_A,
            PyotgwLEDMode.SETPOINT_OVERRIDE_ACTIVE,
            OpenThermSelectLEDMode.SETPOINT_OVERRIDE_ACTIVE,
        ),
        (
            OTGW_LED_B,
            PyotgwLEDMode.CENTRAL_HEATING_ON,
            OpenThermSelectLEDMode.CENTRAL_HEATING_ON,
        ),
        (OTGW_LED_C, PyotgwLEDMode.HOT_WATER_ON, OpenThermSelectLEDMode.HOT_WATER_ON),
        (
            OTGW_LED_D,
            PyotgwLEDMode.COMFORT_MODE_ON,
            OpenThermSelectLEDMode.COMFORT_MODE_ON,
        ),
        (
            OTGW_LED_E,
            PyotgwLEDMode.TX_ERROR_DETECTED,
            OpenThermSelectLEDMode.TX_ERROR_DETECTED,
        ),
        (
            OTGW_LED_F,
            PyotgwLEDMode.RAISED_POWER_MODE_ACTIVE,
            OpenThermSelectLEDMode.RAISED_POWER_MODE_ACTIVE,
        ),
    ],
)
async def test_select_state_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_pyotgw: MagicMock,
    entity_key: str,
    test_value: Any,
    resulting_state: str,
) -> None:
    """Test GPIO mode selector."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        select_entity_id := entity_registry.async_get_entity_id(
            SELECT_DOMAIN,
            OPENTHERM_DOMAIN,
            f"{mock_config_entry.data[CONF_ID]}-{OpenThermDeviceIdentifier.GATEWAY}-{entity_key}",
        )
    ) is not None
    assert hass.states.get(select_entity_id).state == STATE_UNKNOWN

    gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][
        mock_config_entry.data[CONF_ID]
    ]
    async_dispatcher_send(
        hass,
        gw_hub.update_signal,
        {
            OpenThermDeviceIdentifier.BOILER: {},
            OpenThermDeviceIdentifier.GATEWAY: {entity_key: test_value},
            OpenThermDeviceIdentifier.THERMOSTAT: {},
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get(select_entity_id).state == resulting_state
