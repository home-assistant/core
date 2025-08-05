"""Tests for the Peblar number platform."""

from unittest.mock import MagicMock

from peblar import PeblarAuthenticationError, PeblarConnectionError, PeblarError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.peblar.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)


@pytest.mark.parametrize("init_integration", [Platform.NUMBER], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the number entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Ensure all entities are correctly assigned to the Peblar EV charger
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "23-45-A4O-MOF")}
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize("init_integration", [Platform.NUMBER], indirect=True)
@pytest.mark.usefixtures("init_integration", "entity_registry_enabled_by_default")
async def test_number_set_value(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
) -> None:
    """Test the Peblar EV charger numbers."""
    entity_id = "number.peblar_ev_charger_charge_limit"
    mocked_method = mock_peblar.rest_api.return_value.ev_interface
    mocked_method.reset_mock()

    # Test normal happy path number value change
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_VALUE: 10,
        },
        blocking=True,
    )

    assert len(mocked_method.mock_calls) == 2
    mocked_method.mock_calls[0].assert_called_with({"charge_current_limit": 10})


async def test_number_set_value_when_charging_is_suspended(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test handling of setting the charging limit while charging is suspended."""
    entity_id = "number.peblar_ev_charger_charge_limit"

    # Suspend charging
    mock_peblar.rest_api.return_value.ev_interface.return_value.charge_current_limit = 0

    # Setup the config entry
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mocked_method = mock_peblar.rest_api.return_value.ev_interface
    mocked_method.reset_mock()

    # Test normal happy path number value change
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_VALUE: 10,
        },
        blocking=True,
    )

    assert len(mocked_method.mock_calls) == 0

    # Check the state is reflected
    assert (state := hass.states.get(entity_id))
    assert state.state == "10"


@pytest.mark.parametrize(
    ("error", "error_match", "translation_key", "translation_placeholders"),
    [
        (
            PeblarConnectionError("Could not connect"),
            (
                r"An error occurred while communicating "
                r"with the Peblar EV charger: Could not connect"
            ),
            "communication_error",
            {"error": "Could not connect"},
        ),
        (
            PeblarError("Unknown error"),
            (
                r"An unknown error occurred while communicating "
                r"with the Peblar EV charger: Unknown error"
            ),
            "unknown_error",
            {"error": "Unknown error"},
        ),
    ],
)
@pytest.mark.parametrize("init_integration", [Platform.NUMBER], indirect=True)
@pytest.mark.usefixtures("init_integration", "entity_registry_enabled_by_default")
async def test_number_set_value_communication_error(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    error: Exception,
    error_match: str,
    translation_key: str,
    translation_placeholders: dict,
) -> None:
    """Test the Peblar EV charger when a communication error occurs."""
    entity_id = "number.peblar_ev_charger_charge_limit"
    mock_peblar.rest_api.return_value.ev_interface.side_effect = error

    with pytest.raises(
        HomeAssistantError,
        match=error_match,
    ) as excinfo:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_VALUE: 10,
            },
            blocking=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == translation_key
    assert excinfo.value.translation_placeholders == translation_placeholders


@pytest.mark.parametrize("init_integration", [Platform.NUMBER], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_number_set_value_authentication_error(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Peblar EV charger when an authentication error occurs."""
    entity_id = "number.peblar_ev_charger_charge_limit"
    mock_peblar.rest_api.return_value.ev_interface.side_effect = (
        PeblarAuthenticationError("Authentication error")
    )
    mock_peblar.login.side_effect = PeblarAuthenticationError("Authentication error")
    with pytest.raises(
        HomeAssistantError,
        match=(
            r"An authentication failure occurred while communicating "
            r"with the Peblar EV charger"
        ),
    ) as excinfo:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_VALUE: 10,
            },
            blocking=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "authentication_error"
    assert not excinfo.value.translation_placeholders

    # Ensure the device is reloaded on authentication error and triggers
    # a reauthentication flow.
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id


@pytest.mark.parametrize(
    ("restore_state", "restore_native_value", "expected_state"),
    [
        ("10", 10, "10"),
        ("unknown", 10, "unknown"),
        ("unavailable", 10, "unknown"),
        ("10", None, "unknown"),
    ],
)
async def test_restore_state(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
    restore_state: str,
    restore_native_value: int,
    expected_state: str,
) -> None:
    """Test restoring the number state."""
    EXTRA_STORED_DATA = {
        "native_max_value": 16,
        "native_min_value": 6,
        "native_step": 1,
        "native_unit_of_measurement": "A",
        "native_value": restore_native_value,
    }
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State("number.peblar_ev_charger_charge_limit", restore_state),
                EXTRA_STORED_DATA,
            ),
        ),
    )

    # Adjust Peblar client to have an ignored value for the charging limit
    mock_peblar.rest_api.return_value.ev_interface.return_value.charge_current_limit = 0

    # Setup the config entry
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check if state is restored and value is set correctly
    assert (state := hass.states.get("number.peblar_ev_charger_charge_limit"))
    assert state.state == expected_state
