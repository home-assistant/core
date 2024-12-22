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

    # Ensure all entities are correctly assigned to the Peblar device
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
    ("service", "force_single_phase"),
    [
        (SERVICE_TURN_ON, True),
        (SERVICE_TURN_OFF, False),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    force_single_phase: bool,
) -> None:
    """Test the Peblar EV charger switches."""
    entity_id = "switch.peblar_ev_charger_force_single_phase"
    mocked_method = mock_peblar.rest_api.return_value.ev_interface
    mocked_method.reset_mock()

    # Test normal happy path for changing the select option
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mocked_method.mock_calls) == 2
    mocked_method.mock_calls[0].assert_called_with(
        {"force_single_phase": force_single_phase}
    )

    # Test connection error handling
    mocked_method.side_effect = PeblarConnectionError("Could not connect")
    with pytest.raises(
        HomeAssistantError,
        match=(
            r"An error occurred while communicating "
            r"with the Peblar device: Could not connect"
        ),
    ) as excinfo:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "communication_error"
    assert excinfo.value.translation_placeholders == {"error": "Could not connect"}

    # Test unknown error handling
    mocked_method.side_effect = PeblarError("Unknown error")
    with pytest.raises(
        HomeAssistantError,
        match=(
            r"An unknown error occurred while communicating "
            r"with the Peblar device: Unknown error"
        ),
    ) as excinfo:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "unknown_error"
    assert excinfo.value.translation_placeholders == {"error": "Unknown error"}

    # Test authentication error handling
    mocked_method.side_effect = PeblarAuthenticationError("Authentication error")
    mock_peblar.login.side_effect = PeblarAuthenticationError("Authentication error")
    with pytest.raises(
        HomeAssistantError,
        match=(
            r"An authentication failure occurred while communicating "
            r"with the Peblar device"
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
