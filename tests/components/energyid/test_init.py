"""Tests for the EnergyID integration."""

from unittest.mock import AsyncMock, call, patch

import aiohttp
from multidict import CIMultiDict, CIMultiDictProxy
import pytest
from yarl import URL

from homeassistant.components.energyid.__init__ import (
    WebhookDispatcher,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.energyid.const import CONF_WEBHOOK_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .common import (
    MOCK_CONFIG_ENTRY_DATA,
    MockEnergyIDConfigEntry,
    MockEvent,
    MockState,
)


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry happy flow."""
    with patch(
        "homeassistant.components.energyid.__init__.WebhookClientAsync.get_policy",
        return_value=True,
    ):
        entry = MockEnergyIDConfigEntry()
        assert await async_setup_entry(hass=hass, entry=entry) is True

        assert await async_unload_entry(hass=hass, entry=entry) is True


async def test_async_setup_entry_invalid(hass: HomeAssistant) -> None:
    """Test async_setup_entry with invalid config."""
    with patch(
        "homeassistant.components.energyid.__init__.WebhookClientAsync.get_policy",
        side_effect=aiohttp.ClientResponseError(
            aiohttp.RequestInfo(
                url=URL(MOCK_CONFIG_ENTRY_DATA[CONF_WEBHOOK_URL]),
                method="GET",
                headers=CIMultiDictProxy(CIMultiDict({})),
                real_url=URL(MOCK_CONFIG_ENTRY_DATA[CONF_WEBHOOK_URL]),
            ),
            (),
            status=404,
        ),
    ):
        entry = MockEnergyIDConfigEntry()

        # Assert that the setup raises ConfigEntryAuthFailed
        with pytest.raises(ConfigEntryError):
            assert await async_setup_entry(hass=hass, entry=entry) is True


async def test_dispatcher(hass: HomeAssistant) -> None:
    """Test dispatcher."""
    # Create mock client with required attributes
    mock_client = AsyncMock()
    mock_client.webhook_url = "https://example.com/webhook"
    mock_client.post_payload = (
        AsyncMock()
    )  # Ensure the mock client has post_payload method
    # Pass mock_client as runtime_data
    entry = MockEnergyIDConfigEntry(runtime_data=mock_client)
    dispatcher = WebhookDispatcher(hass, entry)

    # Test handle state change when the state is not castable as float
    event = MockEvent(data={"new_state": MockState("not a float")})
    assert await dispatcher.async_handle_state_change(event=event) is False

    # Test handle state change when the URL is not reachable
    event = MockEvent()
    mock_client.post_payload.side_effect = aiohttp.ClientResponseError(
        aiohttp.RequestInfo(
            url=URL(dispatcher.client.webhook_url),
            method="GET",
            headers=CIMultiDictProxy(CIMultiDict({})),
            real_url=URL(dispatcher.client.webhook_url),
        ),
        (),
        status=404,
    )
    assert await dispatcher.async_handle_state_change(event=event) is False

    # Test handle state change of valid event
    event = MockEvent()
    mock_client.post_payload.side_effect = None
    mock_client.post_payload.return_value = True
    assert await dispatcher.async_handle_state_change(event=event) is True

    # Test handle state change of an event that is too soon
    # Since the last event was less than 5 minutes ago, this should return None already
    event = MockEvent()
    assert await dispatcher.async_handle_state_change(event=event) is False


async def test_dispatcher_connection_errors(hass: HomeAssistant) -> None:
    """Test dispatcher handling of connection errors."""
    mock_client = AsyncMock()
    mock_client.webhook_url = "https://example.com/webhook"
    mock_client.post_payload = (
        AsyncMock()
    )  # Ensure the mock client has post_payload method
    entry = MockEnergyIDConfigEntry(runtime_data=mock_client)
    dispatcher = WebhookDispatcher(hass, entry)
    event = MockEvent()

    # Test ClientConnectionError
    mock_client.post_payload.side_effect = aiohttp.ClientConnectionError(
        "Connection refused"
    )
    assert await dispatcher.async_handle_state_change(event=event) is False

    # Test general ClientError
    mock_client.post_payload.side_effect = aiohttp.ClientError("Generic client error")
    assert await dispatcher.async_handle_state_change(event=event) is False


async def test_dispatcher_payload_validation(hass: HomeAssistant) -> None:
    """Test dispatcher payload validation."""
    mock_client = AsyncMock()
    mock_client.webhook_url = "https://example.com/webhook"
    mock_client.post_payload = (
        AsyncMock()
    )  # Ensure the mock client has post_payload method
    entry = MockEnergyIDConfigEntry(runtime_data=mock_client)
    dispatcher = WebhookDispatcher(hass, entry)

    # Test with invalid state attributes
    event = MockEvent(data={"new_state": MockState("42", attributes={})})
    mock_client.post_payload.return_value = True
    assert await dispatcher.async_handle_state_change(event=event) is True


async def test_dispatcher_connection_check_fails(hass: HomeAssistant) -> None:
    """Test dispatcher handling when async_check_connection fails."""
    mock_client = AsyncMock()
    mock_client.webhook_url = "https://example.com/webhook"
    entry = MockEnergyIDConfigEntry(runtime_data=mock_client)
    dispatcher = WebhookDispatcher(hass, entry)

    with patch.object(
        dispatcher, "async_check_connection", return_value=False
    ) as mock_check:
        event = MockEvent()
        result = await dispatcher.async_handle_state_change(event=event)
        assert result is False
        mock_check.assert_called_once()


async def test_dispatcher_connection_check_success(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test dispatcher connection check success when already connected."""
    mock_client = AsyncMock()
    mock_client.webhook_url = "https://example.com/webhook"
    mock_client.get_policy = AsyncMock(return_value=True)
    entry = MockEnergyIDConfigEntry(runtime_data=mock_client)
    dispatcher = WebhookDispatcher(hass, entry)
    dispatcher._connected = True

    caplog.clear()
    result = await dispatcher.async_check_connection()

    # Verify the connection check still occurs and succeeds
    assert result is True
    mock_client.get_policy.assert_called_once()
    # Ensure the success message isn't logged again
    assert "Successfully connected to EnergyID webhook service" not in caplog.text


async def test_async_setup_entry_logs_successful_connection(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test async_setup_entry logs "Successfully connected" on initial setup."""
    with patch(
        "homeassistant.components.energyid.__init__.WebhookClientAsync.get_policy",
        return_value=True,
    ):
        entry = MockEnergyIDConfigEntry()
        caplog.clear()
        assert await async_setup_entry(hass=hass, entry=entry) is True
        assert "Successfully connected to EnergyID webhook service" in caplog.text
        assert await async_unload_entry(hass=hass, entry=entry) is True


async def test_async_setup_entry_initial_connection_fails(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test async_setup_entry when initial connection check fails."""
    # First get_policy succeeds (for setup), but subsequent check fails
    mock_client = AsyncMock()
    mock_client.get_policy = AsyncMock(
        side_effect=[True, aiohttp.ClientConnectionError]
    )

    with patch(
        "homeassistant.components.energyid.__init__.WebhookClientAsync",
        return_value=mock_client,
    ):
        entry = MockEnergyIDConfigEntry()
        caplog.clear()

        # Setup should succeed even though connection check fails
        assert await async_setup_entry(hass=hass, entry=entry) is True

        # Verify warning was logged
        assert "Initial connection to EnergyID webhook service failed" in caplog.text


async def test_dispatcher_retry_logic(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test dispatcher retry logic for failed uploads, including delay timing."""
    mock_client = AsyncMock()
    mock_client.webhook_url = "https://example.com/webhook"
    mock_client.get_policy = AsyncMock(return_value=True)

    # Configure post_payload to fail twice then succeed
    mock_client.post_payload = AsyncMock(
        side_effect=[
            aiohttp.ClientConnectionError("First failure"),
            aiohttp.ClientConnectionError("Second failure"),
            None,  # Success on third try
        ]
    )

    entry = MockEnergyIDConfigEntry(runtime_data=mock_client)
    dispatcher = WebhookDispatcher(hass, entry)
    dispatcher._connected = True  # Skip connection check

    # Mock asyncio.sleep to verify delays without actually waiting
    with patch("asyncio.sleep") as mock_sleep:
        event = MockEvent()
        caplog.clear()

        # Should succeed after retries
        assert await dispatcher.async_handle_state_change(event) is True

        # Verify retry messages were logged
        assert "Upload to EnergyID failed (attempt 1/3)" in caplog.text
        assert "Upload to EnergyID failed (attempt 2/3)" in caplog.text
        assert "Waiting 1 seconds before retrying" in caplog.text
        assert "Waiting 2 seconds before retrying" in caplog.text

        # Verify the exact number of attempts and sleep calls
        assert mock_client.post_payload.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls(
            [
                call(1),  # First retry delay
                call(2),  # Second retry delay
            ]
        )


async def test_dispatcher_lost_connection_logging(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that losing connection logs correctly and updates _connected."""
    mock_client = AsyncMock()
    mock_client.get_policy = AsyncMock(
        side_effect=aiohttp.ClientConnectionError("Connection lost")
    )
    entry = MockEnergyIDConfigEntry(runtime_data=mock_client)
    dispatcher = WebhookDispatcher(hass, entry)

    # Simulate a previously connected state
    dispatcher._connected = True

    caplog.clear()
    result = await dispatcher.async_check_connection()

    assert result is False
    assert dispatcher._connected is False
    assert "Lost connection to EnergyID webhook service: Connection lost" in caplog.text
