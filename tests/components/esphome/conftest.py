"""esphome session fixtures."""
from __future__ import annotations

import asyncio
from asyncio import Event
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aioesphomeapi import (
    APIClient,
    APIVersion,
    DeviceInfo,
    EntityInfo,
    EntityState,
    ReconnectLogic,
    UserService,
)
import pytest
from zeroconf import Zeroconf

from homeassistant.components.esphome import dashboard
from homeassistant.components.esphome.const import (
    CONF_ALLOW_SERVICE_CALLS,
    CONF_DEVICE_NAME,
    CONF_NOISE_PSK,
    DEFAULT_NEW_CONFIG_ALLOW_ALLOW_SERVICE_CALLS,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import DASHBOARD_HOST, DASHBOARD_PORT, DASHBOARD_SLUG

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""


@pytest.fixture(autouse=True)
def esphome_mock_async_zeroconf(mock_async_zeroconf):
    """Auto mock zeroconf."""


@pytest.fixture(autouse=True)
async def load_homeassistant(hass: HomeAssistant) -> None:
    """Load the homeassistant integration."""
    assert await async_setup_component(hass, "homeassistant", {})


@pytest.fixture(autouse=True)
def mock_tts(mock_tts_cache_dir):
    """Auto mock the tts cache."""


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        title="ESPHome Device",
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.2",
            CONF_PORT: 6053,
            CONF_PASSWORD: "pwd",
            CONF_NOISE_PSK: "12345678123456781234567812345678",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def mock_device_info() -> DeviceInfo:
    """Return the default mocked device info."""
    return DeviceInfo(
        uses_password=False,
        name="test",
        legacy_bluetooth_proxy_version=0,
        mac_address="11:22:33:44:55:aa",
        esphome_version="1.0.0",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the ESPHome integration for testing."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_client(mock_device_info) -> APIClient:
    """Mock APIClient."""
    mock_client = Mock(spec=APIClient)

    def mock_constructor(
        address: str,
        port: int,
        password: str | None,
        *,
        client_info: str = "aioesphomeapi",
        keepalive: float = 15.0,
        zeroconf_instance: Zeroconf = None,
        noise_psk: str | None = None,
        expected_name: str | None = None,
    ):
        """Fake the client constructor."""
        mock_client.host = address
        mock_client.port = port
        mock_client.password = password
        mock_client.zeroconf_instance = zeroconf_instance
        mock_client.noise_psk = noise_psk
        return mock_client

    mock_client.side_effect = mock_constructor
    mock_client.device_info = AsyncMock(return_value=mock_device_info)
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.list_entities_services = AsyncMock(return_value=([], []))
    mock_client.api_version = APIVersion(99, 99)

    with patch("homeassistant.components.esphome.APIClient", mock_client), patch(
        "homeassistant.components.esphome.config_flow.APIClient", mock_client
    ):
        yield mock_client


@pytest.fixture
async def mock_dashboard(hass: HomeAssistant):
    """Mock dashboard."""
    data = {"configured": [], "importable": []}
    with patch(
        "esphome_dashboard_api.ESPHomeDashboardAPI.get_devices",
        return_value=data,
    ):
        await dashboard.async_set_dashboard_info(
            hass, DASHBOARD_SLUG, DASHBOARD_HOST, DASHBOARD_PORT
        )
        yield data


class MockESPHomeDevice:
    """Mock an esphome device."""

    def __init__(self, entry: MockConfigEntry) -> None:
        """Init the mock."""
        self.entry = entry
        self.state_callback: Callable[[EntityState], None]
        self.on_disconnect: Callable[[bool], None]
        self.on_connect: Callable[[bool], None]

    def set_state_callback(self, state_callback: Callable[[EntityState], None]) -> None:
        """Set the state callback."""
        self.state_callback = state_callback

    def set_state(self, state: EntityState) -> None:
        """Mock setting state."""
        self.state_callback(state)

    def set_on_disconnect(self, on_disconnect: Callable[[bool], None]) -> None:
        """Set the disconnect callback."""
        self.on_disconnect = on_disconnect

    async def mock_disconnect(self, expected_disconnect: bool) -> None:
        """Mock disconnecting."""
        await self.on_disconnect(expected_disconnect)

    def set_on_connect(self, on_connect: Callable[[], None]) -> None:
        """Set the connect callback."""
        self.on_connect = on_connect

    async def mock_connect(self) -> None:
        """Mock connecting."""
        await self.on_connect()


async def _mock_generic_device_entry(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_device_info: dict[str, Any],
    mock_list_entities_services: tuple[list[EntityInfo], list[UserService]],
    states: list[EntityState],
    entry: MockConfigEntry | None = None,
) -> MockESPHomeDevice:
    if not entry:
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "test.local",
                CONF_PORT: 6053,
                CONF_PASSWORD: "",
            },
            options={
                CONF_ALLOW_SERVICE_CALLS: DEFAULT_NEW_CONFIG_ALLOW_ALLOW_SERVICE_CALLS
            },
        )
        entry.add_to_hass(hass)

    mock_device = MockESPHomeDevice(entry)

    default_device_info = {
        "name": "test",
        "friendly_name": "Test",
        "esphome_version": "1.0.0",
        "mac_address": "11:22:33:44:55:aa",
    }
    device_info = DeviceInfo(**(default_device_info | mock_device_info))

    async def _subscribe_states(callback: Callable[[EntityState], None]) -> None:
        """Subscribe to state."""
        mock_device.set_state_callback(callback)
        for state in states:
            callback(state)

    mock_client.device_info = AsyncMock(return_value=device_info)
    mock_client.subscribe_voice_assistant = AsyncMock(return_value=Mock())
    mock_client.list_entities_services = AsyncMock(
        return_value=mock_list_entities_services
    )
    mock_client.subscribe_states = _subscribe_states

    try_connect_done = Event()

    class MockReconnectLogic(ReconnectLogic):
        """Mock ReconnectLogic."""

        def __init__(self, *args, **kwargs) -> None:
            """Init the mock."""
            super().__init__(*args, **kwargs)
            mock_device.set_on_disconnect(kwargs["on_disconnect"])
            mock_device.set_on_connect(kwargs["on_connect"])
            self._try_connect = self.mock_try_connect

        async def mock_try_connect(self):
            """Set an event when ReconnectLogic._try_connect has been awaited."""
            result = await super()._try_connect()
            try_connect_done.set()
            return result

    with patch(
        "homeassistant.components.esphome.manager.ReconnectLogic", MockReconnectLogic
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        async with asyncio.timeout(2):
            await try_connect_done.wait()

    await hass.async_block_till_done()
    return mock_device


@pytest.fixture
async def mock_voice_assistant_entry(
    hass: HomeAssistant,
    mock_client: APIClient,
):
    """Set up an ESPHome entry with voice assistant."""

    async def _mock_voice_assistant_entry(version: int) -> MockConfigEntry:
        return (
            await _mock_generic_device_entry(
                hass, mock_client, {"voice_assistant_version": version}, ([], []), []
            )
        ).entry

    return _mock_voice_assistant_entry


@pytest.fixture
async def mock_voice_assistant_v1_entry(mock_voice_assistant_entry) -> MockConfigEntry:
    """Set up an ESPHome entry with voice assistant."""
    return await mock_voice_assistant_entry(version=1)


@pytest.fixture
async def mock_voice_assistant_v2_entry(mock_voice_assistant_entry) -> MockConfigEntry:
    """Set up an ESPHome entry with voice assistant."""
    return await mock_voice_assistant_entry(version=2)


@pytest.fixture
async def mock_generic_device_entry(
    hass: HomeAssistant,
) -> Callable[
    [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
    Awaitable[MockConfigEntry],
]:
    """Set up an ESPHome entry and return the MockConfigEntry."""

    async def _mock_device_entry(
        mock_client: APIClient,
        entity_info: list[EntityInfo],
        user_service: list[UserService],
        states: list[EntityState],
    ) -> MockConfigEntry:
        return (
            await _mock_generic_device_entry(
                hass, mock_client, {}, (entity_info, user_service), states
            )
        ).entry

    return _mock_device_entry


@pytest.fixture
async def mock_esphome_device(
    hass: HomeAssistant,
) -> Callable[
    [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
    Awaitable[MockESPHomeDevice],
]:
    """Set up an ESPHome entry and return the MockESPHomeDevice."""

    async def _mock_device(
        mock_client: APIClient,
        entity_info: list[EntityInfo],
        user_service: list[UserService],
        states: list[EntityState],
        entry: MockConfigEntry | None = None,
        device_info: dict[str, Any] | None = None,
    ) -> MockESPHomeDevice:
        return await _mock_generic_device_entry(
            hass,
            mock_client,
            device_info or {},
            (entity_info, user_service),
            states,
            entry,
        )

    return _mock_device
