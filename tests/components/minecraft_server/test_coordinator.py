"""Tests for the Minecraft Server coordinator."""

from unittest.mock import patch

from mcstatus import JavaServer
import pytest

from homeassistant.components.minecraft_server.api import (
    MinecraftServer,
    MinecraftServerType,
)
from homeassistant.components.minecraft_server.const import DEFAULT_NAME
from homeassistant.components.minecraft_server.coordinator import (
    MinecraftServerCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    TEST_ADDRESS,
    TEST_HOST,
    TEST_JAVA_DATA,
    TEST_JAVA_STATUS_RESPONSE,
    TEST_PORT,
)


async def test_update_data(hass: HomeAssistant) -> None:
    """Test successful fetching of updated server data."""
    with patch(
        "mcstatus.server.JavaServer.lookup",
        return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
    ):
        api = MinecraftServer(MinecraftServerType.JAVA_EDITION, TEST_ADDRESS)
        coordinator = MinecraftServerCoordinator(hass, DEFAULT_NAME, api)

    with patch(
        "mcstatus.server.JavaServer.async_status",
        return_value=TEST_JAVA_STATUS_RESPONSE,
    ):
        assert await coordinator._async_update_data() == TEST_JAVA_DATA


async def test_update_data_failure(hass: HomeAssistant) -> None:
    """Test failed fetching of updated server data."""
    with patch(
        "mcstatus.server.JavaServer.lookup",
        return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
    ):
        api = MinecraftServer(MinecraftServerType.JAVA_EDITION, TEST_ADDRESS)
        coordinator = MinecraftServerCoordinator(hass, DEFAULT_NAME, api)

    with patch(
        "mcstatus.server.JavaServer.async_status",
        side_effect=OSError,
    ), pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
