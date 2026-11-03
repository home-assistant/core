"""Tests for the Plugwise Number integration."""

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.plugwise.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er, issue_registry as ir

ADAM_DHW_NUMBER_UNIQUE_ID = "056ee145a816487eaa69243c3280f8bf-max_dhw_temperature"
ADAM_DHW_NUMBER_ISSUE_ID = "deprecated_dhw_temperature_056ee145a816487eaa69243c3280f8bf"


@pytest.mark.usefixtures("mock_smile_adam")
@pytest.mark.parametrize("platforms", [(NUMBER_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_adam_number_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Adam number snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


async def test_adam_temperature_offset_change(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing an Adam temperature_offset number."""
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


@pytest.mark.usefixtures("mock_smile_adam")
async def test_adam_temperature_offset_out_of_bounds_change(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test changing an Adam temperature_offset number beyond limits."""
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
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test changing an existing deprecated DHW number."""
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        NUMBER_DOMAIN,
        DOMAIN,
        ADAM_DHW_NUMBER_UNIQUE_ID,
        config_entry=mock_config_entry,
        suggested_object_id="opentherm_domestic_hot_water_setpoint",
    )
    with patch("homeassistant.components.plugwise.PLATFORMS", [NUMBER_DOMAIN]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("number.opentherm_domestic_hot_water_setpoint")
    assert state
    assert float(state.state) == 60.0
    issue = issue_registry.async_get_issue(DOMAIN, ADAM_DHW_NUMBER_ISSUE_ID)
    assert issue is not None
    assert issue.translation_key == "deprecated_dhw_temperature"

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
        "056ee145a816487eaa69243c3280f8bf", "dhw_temperature", 55.0
    )


@pytest.mark.parametrize("chosen_env", ["m_adam_heating"], indirect=True)
@pytest.mark.parametrize("cooling_present", [False], indirect=True)
async def test_adam_dhw_number_not_created_for_new_install(
    hass: HomeAssistant,
    mock_smile_adam_heat_cool: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the deprecated DHW number is not created for new installations."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.plugwise.PLATFORMS", [NUMBER_DOMAIN]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            NUMBER_DOMAIN, DOMAIN, ADAM_DHW_NUMBER_UNIQUE_ID
        )
        is None
    )
    assert (DOMAIN, ADAM_DHW_NUMBER_ISSUE_ID) not in issue_registry.issues


@pytest.mark.usefixtures("mock_smile_anna")
@pytest.mark.parametrize("chosen_env", ["anna_heatpump_heating"], indirect=True)
@pytest.mark.parametrize("cooling_present", [True], indirect=True)
@pytest.mark.parametrize("platforms", [(NUMBER_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_anna_number_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Anna number snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("chosen_env", ["anna_heatpump_heating"], indirect=True)
@pytest.mark.parametrize("cooling_present", [True], indirect=True)
async def test_anna_boiler_temperature_change(
    hass: HomeAssistant, mock_smile_anna: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing an Anna maximum_boiler_temperature_setpoint number."""
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
        "1cbf783bb11e4a7c8a6843dee3a86927", "boiler_temperature", 65.0
    )
