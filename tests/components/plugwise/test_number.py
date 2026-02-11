"""Tests for the Plugwise Number integration."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("platforms", [(NUMBER_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_adam_number_entities(
    hass: HomeAssistant,
    mock_smile_adam: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Adam number snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


async def test_adam_temperature_offset_change(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing of the temperature_offset number."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.zone_thermostat_jessie_temperature_offset",
            ATTR_VALUE: 1.0,
        },
        blocking=True,
    )

    assert mock_smile_adam.set_number.call_count == 1
    mock_smile_adam.set_number.assert_called_with(
        "6a3bf693d05e48e0b460c815a4fdd09d", "temperature_offset", 1.0
    )


async def test_adam_temperature_offset_out_of_bounds_change(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing of the temperature_offset number beyond limits."""
    with pytest.raises(ServiceValidationError, match="valid range"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.zone_thermostat_jessie_temperature_offset",
                ATTR_VALUE: 3.0,
            },
            blocking=True,
        )


@pytest.mark.parametrize("chosen_env", ["m_adam_heating"], indirect=True)
@pytest.mark.parametrize("cooling_present", [False], indirect=True)
async def test_adam_dhw_setpoint_change(
    hass: HomeAssistant,
    mock_smile_adam_heat_cool: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test changing of number entities."""
    state = hass.states.get("number.opentherm_domestic_hot_water_setpoint")
    assert state
    assert float(state.state) == 60.0

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.opentherm_domestic_hot_water_setpoint",
            ATTR_VALUE: 55,
        },
        blocking=True,
    )

    assert mock_smile_adam_heat_cool.set_number.call_count == 1
    mock_smile_adam_heat_cool.set_number.assert_called_with(
        "056ee145a816487eaa69243c3280f8bf", "max_dhw_temperature", 55.0
    )


@pytest.mark.parametrize("chosen_env", ["anna_heatpump_heating"], indirect=True)
@pytest.mark.parametrize("cooling_present", [True], indirect=True)
@pytest.mark.parametrize("platforms", [(NUMBER_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_anna_number_entities(
    hass: HomeAssistant,
    mock_smile_anna: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Anna number snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("chosen_env", ["anna_heatpump_heating"], indirect=True)
@pytest.mark.parametrize("cooling_present", [True], indirect=True)
async def test_anna_max_boiler_temp_change(
    hass: HomeAssistant, mock_smile_anna: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing of number entities."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.opentherm_maximum_boiler_temperature_setpoint",
            ATTR_VALUE: 65,
        },
        blocking=True,
    )

    assert mock_smile_anna.set_number.call_count == 1
    mock_smile_anna.set_number.assert_called_with(
        "1cbf783bb11e4a7c8a6843dee3a86927", "maximum_boiler_temperature", 65.0
    )
