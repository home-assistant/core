"""Tests for the Aprilaire integration setup."""

from collections.abc import Awaitable, Callable
import logging
from unittest.mock import AsyncMock, Mock, patch

from pyaprilaire.client import AprilaireClient
import pytest

from homeassistant.components.aprilaire import async_setup_entry, async_unload_entry
from homeassistant.components.aprilaire.const import DOMAIN
from homeassistant.components.aprilaire.coordinator import AprilaireCoordinator
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.core import EventBus, HomeAssistant
from homeassistant.util import uuid as uuid_util


@pytest.fixture
def logger() -> logging.Logger:
    """Return a logger."""
    logger = logging.getLogger()
    logger.propagate = False

    return logger


@pytest.fixture
def entry_id() -> str:
    """Return a random ID."""
    return uuid_util.random_uuid_hex()


@pytest.fixture
def hass() -> HomeAssistant:
    """Return a mock HomeAssistant instance."""

    hass_mock = AsyncMock(HomeAssistant)
    hass_mock.data = {}
    hass_mock.config_entries = AsyncMock(ConfigEntries)
    hass_mock.bus = AsyncMock(EventBus)

    return hass_mock


@pytest.fixture
def config_entry(entry_id: str) -> ConfigEntry:
    """Return a mock config entry."""

    config_entry_mock = AsyncMock(ConfigEntry)
    config_entry_mock.data = {"host": "test123", "port": 123}
    config_entry_mock.entry_id = entry_id

    return config_entry_mock


@pytest.fixture
def client() -> AprilaireClient:
    """Return a mock client."""
    return AsyncMock(AprilaireClient)


async def test_async_setup_entry(
    caplog: pytest.LogCaptureFixture,
    client: AprilaireClient,
    config_entry: ConfigEntry,
    entry_id: str,
    hass: HomeAssistant,
    logger: logging.Logger,
) -> None:
    """Test handling of setup with missing MAC address."""

    with patch(
        "pyaprilaire.client.AprilaireClient",
        return_value=client,
    ), caplog.at_level(logging.INFO, logger=logger.name):
        setup_result = await async_setup_entry(hass, config_entry, logger=logger)

    assert setup_result is True

    client.start_listen.assert_called_once()

    assert isinstance(hass.data[DOMAIN][entry_id], AprilaireCoordinator)

    assert caplog.record_tuples == [
        ("root", logging.ERROR, "Missing MAC address, cannot create unique ID"),
        ("root", logging.ERROR, "Failed to wait for ready"),
    ]


async def test_async_setup_entry_ready(
    client: AprilaireClient,
    config_entry: ConfigEntry,
    hass: HomeAssistant,
    logger: logging.Logger,
) -> None:
    """Test setup entry with valid data."""

    async def wait_for_ready(self, ready_callback: Callable[[bool], Awaitable[None]]):
        await ready_callback(True)

    with patch(
        "pyaprilaire.client.AprilaireClient",
        return_value=client,
    ), patch(
        "custom_components.aprilaire.coordinator.AprilaireCoordinator.wait_for_ready",
        new=wait_for_ready,
    ):
        setup_result = await async_setup_entry(hass, config_entry, logger=logger)

    assert setup_result is True


async def test_async_setup_entry_not_ready(
    caplog: pytest.LogCaptureFixture,
    client: AprilaireClient,
    config_entry: ConfigEntry,
    hass: HomeAssistant,
    logger: logging.Logger,
) -> None:
    """Test handling of setup when client is not ready."""

    async def wait_for_ready(self, ready_callback: Callable[[bool], Awaitable[None]]):
        await ready_callback(False)

    with patch(
        "pyaprilaire.client.AprilaireClient",
        return_value=client,
    ), patch(
        "custom_components.aprilaire.coordinator.AprilaireCoordinator.wait_for_ready",
        new=wait_for_ready,
    ), caplog.at_level(logging.INFO, logger=logger.name):
        setup_result = await async_setup_entry(hass, config_entry, logger=logger)

    assert setup_result is True

    client.stop_listen.assert_called_once()

    assert caplog.record_tuples == [("root", logging.ERROR, "Failed to wait for ready")]


async def test_invalid_host(
    caplog: pytest.LogCaptureFixture,
    client: AprilaireClient,
    hass: HomeAssistant,
    logger: logging.Logger,
) -> None:
    """Test setup with invalid host."""

    config_entry_mock = AsyncMock()
    config_entry_mock.data = {}

    with patch(
        "pyaprilaire.client.AprilaireClient",
        return_value=client,
    ), caplog.at_level(logging.INFO, logger=logger.name):
        setup_result = await async_setup_entry(hass, config_entry_mock, logger=logger)

    assert setup_result is False

    client.start_listen.assert_not_called()

    assert caplog.record_tuples == [("root", logging.ERROR, "Invalid host None")]


async def test_invalid_port(
    caplog: pytest.LogCaptureFixture,
    client: AprilaireClient,
    hass: HomeAssistant,
    logger: logging.Logger,
) -> None:
    """Test setup with invalid port."""

    config_entry_mock = AsyncMock()
    config_entry_mock.data = {"host": "test123"}

    with patch(
        "pyaprilaire.client.AprilaireClient",
        return_value=client,
    ), caplog.at_level(logging.INFO, logger=logger.name):
        setup_result = await async_setup_entry(hass, config_entry_mock, logger=logger)

    assert setup_result is False

    client.start_listen.assert_not_called()

    assert caplog.record_tuples == [("root", logging.ERROR, "Invalid port None")]


async def test_unload_entry_ok(
    client: AprilaireClient,
    config_entry: ConfigEntry,
    hass: HomeAssistant,
    logger: logging.Logger,
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
        "custom_components.aprilaire.coordinator.AprilaireCoordinator.wait_for_ready",
        new=wait_for_ready,
    ), patch(
        "custom_components.aprilaire.coordinator.AprilaireCoordinator.stop_listen",
        new=stop_listen_mock,
    ):
        await async_setup_entry(hass, config_entry, logger=logger)

        unload_result = await async_unload_entry(hass, config_entry)

    hass.config_entries.async_unload_platforms.assert_called_once()

    assert unload_result is True

    stop_listen_mock.assert_called_once()


async def test_unload_entry_not_ok(
    client: AprilaireClient,
    config_entry: ConfigEntry,
    hass: HomeAssistant,
    logger: logging.Logger,
) -> None:
    """Test handling of unload failure."""

    async def wait_for_ready(self, ready_callback: Callable[[bool], Awaitable[None]]):
        await ready_callback(True)

    with patch(
        "pyaprilaire.client.AprilaireClient",
        return_value=client,
    ), patch(
        "custom_components.aprilaire.coordinator.AprilaireCoordinator.wait_for_ready",
        new=wait_for_ready,
    ):
        await async_setup_entry(hass, config_entry, logger=logger)

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

    unload_result = await async_unload_entry(hass, config_entry)

    hass.config_entries.async_unload_platforms.assert_called_once()

    assert unload_result is False
