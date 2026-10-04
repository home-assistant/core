"""Test opentherm_gw number entities."""

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.opentherm_gw import DOMAIN
from homeassistant.components.opentherm_gw.const import OpenThermDeviceIdentifier
from homeassistant.const import ATTR_ENTITY_ID, CONF_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("pyotgw_function", "entity_key"),
    [
        ("set_control_setpoint", "control_setpoint_override"),
        ("set_control_setpoint_2", "control_setpoint_override_2"),
    ],
)
async def test_control_setpoint_number_set_value(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_pyotgw: MagicMock,
    pyotgw_function: str,
    entity_key: str,
) -> None:
    """Test control setpoint override numbers."""

    setattr(mock_pyotgw.return_value, pyotgw_function, AsyncMock(side_effect=[10.5, 0]))
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        number_entity_id := entity_registry.async_get_entity_id(
            NUMBER_DOMAIN,
            DOMAIN,
            f"{mock_config_entry.data[CONF_ID]}-{OpenThermDeviceIdentifier.GATEWAY}-{entity_key}",
        )
    ) is not None

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: number_entity_id,
            ATTR_VALUE: 10.5,
        },
        blocking=True,
    )

    assert hass.states.get(number_entity_id).state == "10.5"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: number_entity_id,
            ATTR_VALUE: 0,
        },
        blocking=True,
    )
    assert hass.states.get(number_entity_id).state == STATE_UNKNOWN

    mock_function = getattr(mock_pyotgw.return_value, pyotgw_function)
    assert mock_function.await_count == 2
    mock_function.assert_has_awaits([call(10.5), call(0)])

    # Mock gets awaited during exit for safety reasons, hence we provide a generic
    # return value to prevent triggering a StopAsyncIteration error.
    setattr(mock_pyotgw.return_value, pyotgw_function, AsyncMock(return_value=0))


@pytest.mark.parametrize(
    "entity_key", ["control_setpoint_override", "control_setpoint_override_2"]
)
async def test_number_added_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_pyotgw: MagicMock,
    entity_key: str,
) -> None:
    """Test number gets added in disabled state."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        number_entity_id := entity_registry.async_get_entity_id(
            NUMBER_DOMAIN,
            DOMAIN,
            f"{mock_config_entry.data[CONF_ID]}-{OpenThermDeviceIdentifier.GATEWAY}-{entity_key}",
        )
    ) is not None

    assert (entity_entry := entity_registry.async_get(number_entity_id)) is not None
    assert entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
