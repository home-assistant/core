"""Test the Threema Gateway integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from threema.gateway.exception import GatewayServerError

from homeassistant.components.threema.client import ThreemaAuthError
from homeassistant.components.threema.const import (
    CONF_API_SECRET,
    CONF_GATEWAY_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries on connection error (ConfigEntryNotReady)."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.threema.client.Connection", autospec=True
    ) as connection_class:
        connection = MagicMock()
        connection.__aenter__ = AsyncMock(return_value=connection)
        connection.__aexit__ = AsyncMock(return_value=None)
        connection.get_credits = AsyncMock(side_effect=Exception("Connection refused"))
        connection_class.return_value = connection

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails on auth error (ConfigEntryAuthFailed)."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.threema.ThreemaAPIClient.validate_credentials",
        side_effect=ThreemaAuthError("Invalid credentials"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_send_message_service(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_send: MagicMock,
) -> None:
    """Test the send_message service call."""
    await hass.services.async_call(
        DOMAIN,
        "send_message",
        {
            "config_entry_id": init_integration.entry_id,
            "recipient": "ABCD1234",
            "message": "Hello from tests!",
        },
        blocking=True,
    )

    # Verify SimpleTextMessage was used (no private key)
    mock_send.simple.assert_called_once()


async def test_send_message_service_auto_select(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_send: MagicMock,
) -> None:
    """Test send_message service auto-selects entry when not specified."""
    await hass.services.async_call(
        DOMAIN,
        "send_message",
        {
            "recipient": "ABCD1234",
            "message": "Hello from tests!",
        },
        blocking=True,
    )

    mock_send.simple.assert_called_once()


async def test_send_message_service_entry_not_found(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test send_message service with invalid entry ID."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {
                "config_entry_id": "nonexistent_entry_id",
                "recipient": "ABCD1234",
                "message": "Hello!",
            },
            blocking=True,
        )


async def test_send_message_service_no_loaded_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test send_message service raises when no entries are loaded."""
    mock_config_entry.add_to_hass(hass)

    # Setup then unload so service is registered but no entry is loaded
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {
                "recipient": "ABCD1234",
                "message": "Hello!",
            },
            blocking=True,
        )


async def test_send_message_service_send_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test send_message service handles send failure."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.threema.client.SimpleTextMessage", autospec=True
    ) as simple_mock:
        simple_instance = MagicMock()
        simple_instance.send = AsyncMock(side_effect=Exception("Network error"))
        simple_mock.return_value = simple_instance

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                "send_message",
                {
                    "recipient": "ABCD1234",
                    "message": "Hello!",
                },
                blocking=True,
            )


async def test_send_message_service_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test send_message service handles auth failure during send."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.threema.client.SimpleTextMessage", autospec=True
    ) as simple_mock:
        simple_instance = MagicMock()
        simple_instance.send = AsyncMock(side_effect=GatewayServerError(status=401))
        simple_mock.return_value = simple_instance

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                "send_message",
                {
                    "recipient": "ABCD1234",
                    "message": "Hello!",
                },
                blocking=True,
            )


async def test_send_message_service_e2e(
    hass: HomeAssistant,
    mock_config_entry_with_keys: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test send_message service uses E2E TextMessage when private key is set."""
    mock_config_entry_with_keys.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_keys.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "send_message",
        {
            "config_entry_id": mock_config_entry_with_keys.entry_id,
            "recipient": "ABCD1234",
            "message": "Hello E2E!",
        },
        blocking=True,
    )

    mock_send.e2e.assert_called_once()


async def test_send_message_service_multiple_entries(
    hass: HomeAssistant,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test send_message service raises when multiple entries and no ID specified."""
    entry1 = MockConfigEntry(
        title="Threema *FIRST01",
        domain=DOMAIN,
        data={
            CONF_GATEWAY_ID: "*FIRST01",
            CONF_API_SECRET: "first_secret",
        },
        unique_id="*FIRST01",
    )
    entry2 = MockConfigEntry(
        title="Threema *SECOND1",
        domain=DOMAIN,
        data={
            CONF_GATEWAY_ID: "*SECOND1",
            CONF_API_SECRET: "second_secret",
        },
        unique_id="*SECOND1",
    )
    entry1.add_to_hass(hass)
    entry2.add_to_hass(hass)

    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert entry1.state is ConfigEntryState.LOADED
    assert entry2.state is ConfigEntryState.LOADED

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {
                "recipient": "ABCD1234",
                "message": "Hello!",
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "multiple_entries_found"
