"""Tests for the Peblar switch platform."""

from unittest.mock import MagicMock

from peblar import PeblarAuthenticationError, PeblarConnectionError, PeblarError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.peblar.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = [
    pytest.mark.parametrize("init_integration", [Platform.SWITCH], indirect=True),
    pytest.mark.usefixtures("init_integration"),
]


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch entities."""
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


@pytest.mark.parametrize(
    ("service", "entity_id", "parameter", "parameter_value"),
    [
        (
            SERVICE_TURN_ON,
            "switch.peblar_ev_charger_force_single_phase",
            "force_single_phase",
            True,
        ),
        (
            SERVICE_TURN_OFF,
            "switch.peblar_ev_charger_force_single_phase",
            "force_single_phase",
            False,
        ),
        (
            SERVICE_TURN_ON,
            "switch.peblar_ev_charger_charge",
            "charge_current_limit",
            16,
        ),
        (
            SERVICE_TURN_OFF,
            "switch.peblar_ev_charger_charge",
            "charge_current_limit",
            0,
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    service: str,
    entity_id: str,
    parameter: str,
    parameter_value: bool | int,
) -> None:
    """Test the Peblar EV charger switches."""
    mocked_method = mock_peblar.rest_api.return_value.ev_interface
    mocked_method.reset_mock()

    # Test normal happy path for changing the switch state
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mocked_method.mock_calls) == 2
    mocked_method.mock_calls[0].assert_called_with({parameter: parameter_value})


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
@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_communication_error(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    error: Exception,
    error_match: str,
    translation_key: str,
    translation_placeholders: dict,
    service: str,
) -> None:
    """Test the Peblar EV charger when a communication error occurs."""
    entity_id = "switch.peblar_ev_charger_force_single_phase"
    mock_peblar.rest_api.return_value.ev_interface.side_effect = error
    with pytest.raises(
        HomeAssistantError,
        match=error_match,
    ) as excinfo:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == translation_key
    assert excinfo.value.translation_placeholders == translation_placeholders


@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_switch_authentication_error(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test the Peblar EV charger when an authentication error occurs."""
    entity_id = "switch.peblar_ev_charger_force_single_phase"
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
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
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
