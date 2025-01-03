"""Tests for the EnergyID integration."""

from unittest.mock import patch

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
    dispatcher = WebhookDispatcher(hass, MockEnergyIDConfigEntry())

    # Test handle state change when the state is not castable as float
    event = MockEvent(data={"new_state": MockState("not a float")})
    assert await dispatcher.async_handle_state_change(event=event) is False

    # Test handle state change when the URL is not reachable
    event = MockEvent()
    with patch(
        "homeassistant.components.energyid.__init__.WebhookClientAsync.post_payload",
        side_effect=aiohttp.ClientResponseError(
            aiohttp.RequestInfo(
                url=URL(dispatcher.client.webhook_url),
                method="GET",
                headers=CIMultiDictProxy(CIMultiDict({})),
                real_url=URL(dispatcher.client.webhook_url),
            ),
            (),
            status=404,
        ),
    ):
        assert await dispatcher.async_handle_state_change(event=event) is False

    # Test handle state change of valid event
    event = MockEvent()
    with patch(
        "homeassistant.components.energyid.__init__.WebhookClientAsync.post_payload",
        return_value=True,
    ):
        assert await dispatcher.async_handle_state_change(event=event) is True

    # Test handle state change of an event that is too soon
    # Since the last event was less than 5 minutes ago, this should return None already
    event = MockEvent()
    assert await dispatcher.async_handle_state_change(event=event) is False


async def test_dispatcher_connection_errors(hass: HomeAssistant) -> None:
    """Test dispatcher handling of connection errors."""
    dispatcher = WebhookDispatcher(hass, MockEnergyIDConfigEntry())
    event = MockEvent()

    # Test ClientConnectionError
    with patch(
        "homeassistant.components.energyid.__init__.WebhookClientAsync.post_payload",
        side_effect=aiohttp.ClientConnectionError("Connection refused"),
    ):
        assert await dispatcher.async_handle_state_change(event=event) is False

    # Test general ClientError
    with patch(
        "homeassistant.components.energyid.__init__.WebhookClientAsync.post_payload",
        side_effect=aiohttp.ClientError("Generic client error"),
    ):
        assert await dispatcher.async_handle_state_change(event=event) is False


async def test_dispatcher_payload_validation(hass: HomeAssistant) -> None:
    """Test dispatcher payload validation."""
    dispatcher = WebhookDispatcher(hass, MockEnergyIDConfigEntry())

    # Test with invalid state attributes
    event = MockEvent(data={"new_state": MockState("42", attributes={})})
    with patch(
        "homeassistant.components.energyid.__init__.WebhookClientAsync.post_payload",
        return_value=True,
    ):
        assert await dispatcher.async_handle_state_change(event=event) is True
