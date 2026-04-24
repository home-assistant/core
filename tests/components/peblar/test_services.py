"""Tests for the Peblar integration services."""

from unittest.mock import MagicMock

from peblar import PeblarRfidToken
import pytest

from homeassistant.components.peblar.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_peblar: MagicMock,
) -> MockConfigEntry:
    """Set up the Peblar integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


async def test_services_registered_on_setup(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test that RFID services are registered when entry is loaded."""
    assert hass.services.has_service(DOMAIN, "list_rfid_tokens")
    assert hass.services.has_service(DOMAIN, "add_rfid_token")
    assert hass.services.has_service(DOMAIN, "remove_rfid_token")


async def test_services_removed_on_last_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test RFID services removed when last entry unloads."""
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "list_rfid_tokens")
    assert not hass.services.has_service(DOMAIN, "add_rfid_token")
    assert not hass.services.has_service(DOMAIN, "remove_rfid_token")


async def test_services_not_removed_while_other_entry_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test RFID services persist when a second entry is still loaded."""
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry.data,
        unique_id="second-charger",
    )
    second_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(second_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "list_rfid_tokens")


async def test_list_rfid_tokens(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test list_rfid_tokens returns token list."""
    mock_peblar.rfid_tokens.return_value = [
        PeblarRfidToken(
            rfid_token_uid="AA:BB:CC:DD",
            rfid_token_description="My Card",
        ),
        PeblarRfidToken(
            rfid_token_uid="11:22:33:44",
            rfid_token_description="Work Badge",
        ),
    ]

    result = await hass.services.async_call(
        DOMAIN,
        "list_rfid_tokens",
        {"config_entry_id": init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    assert result == {
        "tokens": [
            {"uid": "AA:BB:CC:DD", "description": "My Card"},
            {"uid": "11:22:33:44", "description": "Work Badge"},
        ]
    }
    mock_peblar.rfid_tokens.assert_called_once_with()


async def test_add_rfid_token(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test add_rfid_token calls library with correct args."""
    await hass.services.async_call(
        DOMAIN,
        "add_rfid_token",
        {
            "config_entry_id": init_integration.entry_id,
            "uid": "AA:BB:CC:DD",
            "description": "My Card",
        },
        blocking=True,
    )

    mock_peblar.add_rfid_token.assert_called_once_with(
        rfid_token_uid="AA:BB:CC:DD",
        rfid_token_description="My Card",
    )


async def test_remove_rfid_token(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test remove_rfid_token calls library with correct args."""
    await hass.services.async_call(
        DOMAIN,
        "remove_rfid_token",
        {
            "config_entry_id": init_integration.entry_id,
            "uid": "AA:BB:CC:DD",
        },
        blocking=True,
    )

    mock_peblar.delete_rfid_token.assert_called_once_with(uid="AA:BB:CC:DD")


async def test_invalid_config_entry_raises(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test service raises ServiceValidationError for unknown entry ID."""
    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            "list_rfid_tokens",
            {"config_entry_id": "nonexistent-entry-id"},
            blocking=True,
            return_response=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "invalid_config_entry"
