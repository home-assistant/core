"""Tests for the Aprilaire integration setup."""

from collections.abc import Awaitable, Callable
import contextlib
import logging
from unittest.mock import AsyncMock, Mock, patch

from pyaprilaire.client import AprilaireClient
import pytest

from homeassistant.components.aprilaire import async_setup_entry, async_unload_entry
from homeassistant.components.aprilaire.const import DOMAIN
from homeassistant.components.aprilaire.coordinator import AprilaireCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


@pytest.fixture
def logger() -> logging.Logger:
    """Return a logger."""
    logger = logging.getLogger(__name__)
    logger.propagate = False

    return logger


@pytest.fixture
def config_entry() -> ConfigEntry:
    """Return a mock config entry."""

    config_entry_mock = AsyncMock(ConfigEntry)
    config_entry_mock.data = {"host": "test123", "port": 123}
    config_entry_mock.unique_id = "1:2:3:4:5:6"

    return config_entry_mock


@pytest.fixture
def client() -> AprilaireClient:
    """Return a mock client."""
    client = AsyncMock(AprilaireClient)
    client.data = {}
    client.data["mac_address"] = "1:2:3:4:5:6"

    return client


async def test_async_setup_entry(
    client: AprilaireClient,
    config_entry: ConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test handling of setup with missing MAC address."""

    with patch(
        "pyaprilaire.client.AprilaireClient",
        return_value=client,
    ), contextlib.suppress(Exception):
        setup_result = await async_setup_entry(hass, config_entry)

        assert setup_result is True

        client.start_listen.assert_called_once()

        assert isinstance(hass.data[DOMAIN]["1:2:3:4:5:6"], AprilaireCoordinator)


async def test_async_setup_entry_ready(
    client: AprilaireClient,
    config_entry: ConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test setup entry with valid data."""

    async def wait_for_ready(self, ready_callback: Callable[[bool], Awaitable[None]]):
        await ready_callback(True)

    with patch(
        "pyaprilaire.client.AprilaireClient",
        return_value=client,
    ), patch(
        "homeassistant.components.aprilaire.coordinator.AprilaireCoordinator.wait_for_ready",
        new=wait_for_ready,
    ):
        setup_result = await async_setup_entry(hass, config_entry)

    assert setup_result is True


async def test_async_setup_entry_not_ready(
    client: AprilaireClient,
    config_entry: ConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test handling of setup when client is not ready."""

    async def wait_for_ready(self, ready_callback: Callable[[bool], Awaitable[None]]):
        await ready_callback(False)

    with patch(
        "pyaprilaire.client.AprilaireClient",
        return_value=client,
    ), patch(
        "homeassistant.components.aprilaire.coordinator.AprilaireCoordinator.wait_for_ready",
        new=wait_for_ready,
    ), pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, config_entry)

    client.stop_listen.assert_called_once()


async def test_unload_entry_ok(
    client: AprilaireClient,
    config_entry: ConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test unloading the config entry."""

    async def wait_for_ready(self, ready_callback: Callable[[bool], Awaitable[None]]):
        await ready_callback(True)

    stop_listen_mock = Mock()

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    with patch(
        "pyaprilaire.client.AprilaireClient",
        return_value=client,
    ), patch(
        "homeassistant.components.aprilaire.coordinator.AprilaireCoordinator.wait_for_ready",
        new=wait_for_ready,
    ), patch(
        "homeassistant.components.aprilaire.coordinator.AprilaireCoordinator.stop_listen",
        new=stop_listen_mock,
    ):
        await async_setup_entry(hass, config_entry)

        unload_result = await async_unload_entry(hass, config_entry)

    hass.config_entries.async_unload_platforms.assert_called_once()

    assert unload_result is True

    stop_listen_mock.assert_called_once()


async def test_unload_entry_not_ok(
    client: AprilaireClient,
    config_entry: ConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test handling of unload failure."""

    async def wait_for_ready(self, ready_callback: Callable[[bool], Awaitable[None]]):
        await ready_callback(True)

    with patch(
        "pyaprilaire.client.AprilaireClient",
        return_value=client,
    ), patch(
        "homeassistant.components.aprilaire.coordinator.AprilaireCoordinator.wait_for_ready",
        new=wait_for_ready,
    ):
        await async_setup_entry(hass, config_entry)

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

    unload_result = await async_unload_entry(hass, config_entry)

    hass.config_entries.async_unload_platforms.assert_called_once()

    assert unload_result is False


async def test_stop_triggers_stop_listen(
    client: AprilaireClient,
    config_entry: ConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test that the client stops listening when Home Assistant is stopped."""

    async def wait_for_ready(self, ready_callback: Callable[[bool], Awaitable[None]]):
        await ready_callback(True)

    with patch(
        "pyaprilaire.client.AprilaireClient",
        return_value=client,
    ), patch(
        "homeassistant.components.aprilaire.coordinator.AprilaireCoordinator.wait_for_ready",
        new=wait_for_ready,
    ):
        await async_setup_entry(hass, config_entry)

    hass.bus.fire(EVENT_HOMEASSISTANT_STOP)

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    client.stop_listen.assert_called_once()
