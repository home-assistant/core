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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = [
    pytest.mark.parametrize("init_integration", [Platform.NUMBER], indirect=True),
    pytest.mark.usefixtures("init_integration"),
]


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the number entities."""
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
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
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_VALUE: 10,
            },
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
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_VALUE: 10,
            },
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
