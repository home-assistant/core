"""esphome session fixtures."""

from __future__ import annotations

import asyncio
from asyncio import Event
from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aioesphomeapi import (
    APIClient,
    APIVersion,
    BluetoothProxyFeature,
    DeviceInfo,
    EntityInfo,
    EntityState,
    HomeassistantServiceCall,
    ReconnectLogic,
    UserService,
    VoiceAssistantAudioSettings,
    VoiceAssistantFeature,
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

_ONE_SECOND = 16000 * 2  # 16Khz 16-bit


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture(autouse=True)
def esphome_mock_async_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Auto mock zeroconf."""


@pytest.fixture(autouse=True)
async def load_homeassistant(hass: HomeAssistant) -> None:
    """Load the homeassistant integration."""
    assert await async_setup_component(hass, "homeassistant", {})


@pytest.fixture(autouse=True)
def mock_tts(mock_tts_cache_dir: Path) -> None:
    """Auto mock the tts cache."""


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        title="ESPHome Device",
        entry_id="08d821dc059cf4f645cb024d32c8e708",
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.2",
            CONF_PORT: 6053,
            CONF_PASSWORD: "pwd",
            CONF_NOISE_PSK: "12345678123456781234567812345678",
            CONF_DEVICE_NAME: "test",
        },
        # ESPHome unique ids are lower case
        unique_id="11:22:33:44:55:aa",
    )
    config_entry.add_to_hass(hass)
    return config_entry


class BaseMockReconnectLogic(ReconnectLogic):
    """Mock ReconnectLogic."""

    def stop_callback(self) -> None:
        """Stop the reconnect logic."""
        # For the purposes of testing, we don't want to wait
        # for the reconnect logic to finish trying to connect
        self._cancel_connect("forced disconnect from test")
        self._is_stopped = True

    async def stop(self) -> None:
        """Stop the reconnect logic."""
        self.stop_callback()


@pytest.fixture
def mock_device_info() -> DeviceInfo:
    """Return the default mocked device info."""
    return DeviceInfo(
        uses_password=False,
        name="test",
        legacy_bluetooth_proxy_version=0,
        # ESPHome mac addresses are UPPER case
        mac_address="11:22:33:44:55:AA",
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
    mock_client.address = "127.0.0.1"
    mock_client.api_version = APIVersion(99, 99)

    with (
        patch(
            "homeassistant.components.esphome.manager.ReconnectLogic",
            BaseMockReconnectLogic,
        ),
        patch("homeassistant.components.esphome.APIClient", mock_client),
        patch("homeassistant.components.esphome.config_flow.APIClient", mock_client),
    ):
        yield mock_client


@pytest.fixture
async def mock_dashboard(hass: HomeAssistant) -> AsyncGenerator[dict[str, Any]]:
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

    def __init__(
        self, entry: MockConfigEntry, client: APIClient, device_info: DeviceInfo
    ) -> None:
        """Init the mock."""
        self.entry = entry
        self.client = client
        self.state_callback: Callable[[EntityState], None]
        self.service_call_callback: Callable[[HomeassistantServiceCall], None]
        self.on_disconnect: Callable[[bool], None]
        self.on_connect: Callable[[bool], None]
        self.on_connect_error: Callable[[Exception], None]
        self.home_assistant_state_subscription_callback: Callable[
            [str, str | None], None
        ]
        self.home_assistant_state_request_callback: Callable[[str, str | None], None]
        self.voice_assistant_handle_start_callback: Callable[
            [str, int, VoiceAssistantAudioSettings, str | None],
            Coroutine[Any, Any, int | None],
        ]
        self.voice_assistant_handle_stop_callback: Callable[
            [], Coroutine[Any, Any, None]
        ]
        self.voice_assistant_handle_audio_callback: (
            Callable[
                [bytes],
                Coroutine[Any, Any, None],
            ]
            | None
        )
        self.device_info = device_info

    def set_state_callback(self, state_callback: Callable[[EntityState], None]) -> None:
        """Set the state callback."""
        self.state_callback = state_callback

    def set_service_call_callback(
        self, callback: Callable[[HomeassistantServiceCall], None]
    ) -> None:
        """Set the service call callback."""
        self.service_call_callback = callback

    def mock_service_call(self, service_call: HomeassistantServiceCall) -> None:
        """Mock a service call."""
        self.service_call_callback(service_call)

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

    def set_on_connect_error(
        self, on_connect_error: Callable[[Exception], None]
    ) -> None:
        """Set the connect error callback."""
        self.on_connect_error = on_connect_error

    async def mock_connect(self) -> None:
        """Mock connecting."""
        await self.on_connect()

    async def mock_connect_error(self, exc: Exception) -> None:
        """Mock connect error."""
        await self.on_connect_error(exc)

    def set_home_assistant_state_subscription_callback(
        self,
        on_state_sub: Callable[[str, str | None], None],
        on_state_request: Callable[[str, str | None], None],
    ) -> None:
        """Set the state call callback."""
        self.home_assistant_state_subscription_callback = on_state_sub
        self.home_assistant_state_request_callback = on_state_request

    def mock_home_assistant_state_subscription(
        self, entity_id: str, attribute: str | None
    ) -> None:
        """Mock a state subscription."""
        self.home_assistant_state_subscription_callback(entity_id, attribute)

    def mock_home_assistant_state_request(
        self, entity_id: str, attribute: str | None
    ) -> None:
        """Mock a state request."""
        self.home_assistant_state_request_callback(entity_id, attribute)

    def set_subscribe_voice_assistant_callbacks(
        self,
        handle_start: Callable[
            [str, int, VoiceAssistantAudioSettings, str | None],
            Coroutine[Any, Any, int | None],
        ],
        handle_stop: Callable[[], Coroutine[Any, Any, None]],
        handle_audio: (
            Callable[
                [bytes],
                Coroutine[Any, Any, None],
            ]
            | None
        ) = None,
    ) -> None:
        """Set the voice assistant subscription callbacks."""
        self.voice_assistant_handle_start_callback = handle_start
        self.voice_assistant_handle_stop_callback = handle_stop
        self.voice_assistant_handle_audio_callback = handle_audio

    async def mock_voice_assistant_handle_start(
        self,
        conversation_id: str,
        flags: int,
        settings: VoiceAssistantAudioSettings,
        wake_word_phrase: str | None,
    ) -> int | None:
        """Mock voice assistant handle start."""
        return await self.voice_assistant_handle_start_callback(
            conversation_id, flags, settings, wake_word_phrase
        )

    async def mock_voice_assistant_handle_stop(self) -> None:
        """Mock voice assistant handle stop."""
        await self.voice_assistant_handle_stop_callback()

    async def mock_voice_assistant_handle_audio(self, audio: bytes) -> None:
        """Mock voice assistant handle audio."""
        assert self.voice_assistant_handle_audio_callback is not None
        await self.voice_assistant_handle_audio_callback(audio)


async def _mock_generic_device_entry(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_device_info: dict[str, Any],
    mock_list_entities_services: tuple[list[EntityInfo], list[UserService]],
    states: list[EntityState],
    entry: MockConfigEntry | None = None,
    hass_storage: dict[str, Any] | None = None,
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

    default_device_info = {
        "name": "test",
        "friendly_name": "Test",
        "esphome_version": "1.0.0",
        "mac_address": "11:22:33:44:55:AA",
    }
    device_info = DeviceInfo(**(default_device_info | mock_device_info))

    if hass_storage:
        storage_key = f"{DOMAIN}.{entry.entry_id}"
        hass_storage[storage_key] = {
            "version": 1,
            "minor_version": 1,
            "key": storage_key,
            "data": {
                "device_info": device_info.to_dict(),
            },
        }

    mock_device = MockESPHomeDevice(entry, mock_client, device_info)

    def _subscribe_states(callback: Callable[[EntityState], None]) -> None:
        """Subscribe to state."""
        mock_device.set_state_callback(callback)
        for state in states:
            callback(state)

    def _subscribe_service_calls(
        callback: Callable[[HomeassistantServiceCall], None],
    ) -> None:
        """Subscribe to service calls."""
        mock_device.set_service_call_callback(callback)

    def _subscribe_home_assistant_states(
        on_state_sub: Callable[[str, str | None], None],
        on_state_request: Callable[[str, str | None], None],
    ) -> None:
        """Subscribe to home assistant states."""
        mock_device.set_home_assistant_state_subscription_callback(
            on_state_sub, on_state_request
        )

    def _subscribe_voice_assistant(
        *,
        handle_start: Callable[
            [str, int, VoiceAssistantAudioSettings, str | None],
            Coroutine[Any, Any, int | None],
        ],
        handle_stop: Callable[[], Coroutine[Any, Any, None]],
        handle_audio: (
            Callable[
                [bytes],
                Coroutine[Any, Any, None],
            ]
            | None
        ) = None,
    ) -> Callable[[], None]:
        """Subscribe to voice assistant."""
        mock_device.set_subscribe_voice_assistant_callbacks(
            handle_start, handle_stop, handle_audio
        )

        def unsub():
            pass

        return unsub

    mock_client.device_info = AsyncMock(return_value=mock_device.device_info)
    mock_client.subscribe_voice_assistant = _subscribe_voice_assistant
    mock_client.list_entities_services = AsyncMock(
        return_value=mock_list_entities_services
    )
    mock_client.subscribe_states = _subscribe_states
    mock_client.subscribe_service_calls = _subscribe_service_calls
    mock_client.subscribe_home_assistant_states = _subscribe_home_assistant_states

    try_connect_done = Event()

    class MockReconnectLogic(BaseMockReconnectLogic):
        """Mock ReconnectLogic."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Init the mock."""
            super().__init__(*args, **kwargs)
            mock_device.set_on_disconnect(kwargs["on_disconnect"])
            mock_device.set_on_connect(kwargs["on_connect"])
            mock_device.set_on_connect_error(kwargs["on_connect_error"])
            self._try_connect = self.mock_try_connect

        async def mock_try_connect(self):
            """Set an event when ReconnectLogic._try_connect has been awaited."""
            result = await super()._try_connect()
            try_connect_done.set()
            return result

        def stop_callback(self) -> None:
            """Stop the reconnect logic."""
            # For the purposes of testing, we don't want to wait
            # for the reconnect logic to finish trying to connect
            self._cancel_connect("forced disconnect from test")
            self._is_stopped = True

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

    async def _mock_voice_assistant_entry(
        voice_assistant_feature_flags: VoiceAssistantFeature,
    ) -> MockConfigEntry:
        return (
            await _mock_generic_device_entry(
                hass,
                mock_client,
                {"voice_assistant_feature_flags": voice_assistant_feature_flags},
                ([], []),
                [],
            )
        ).entry

    return _mock_voice_assistant_entry


@pytest.fixture
async def mock_voice_assistant_v1_entry(mock_voice_assistant_entry) -> MockConfigEntry:
    """Set up an ESPHome entry with voice assistant."""
    return await mock_voice_assistant_entry(
        voice_assistant_feature_flags=VoiceAssistantFeature.VOICE_ASSISTANT
    )


@pytest.fixture
async def mock_voice_assistant_v2_entry(mock_voice_assistant_entry) -> MockConfigEntry:
    """Set up an ESPHome entry with voice assistant."""
    return await mock_voice_assistant_entry(
        voice_assistant_feature_flags=VoiceAssistantFeature.VOICE_ASSISTANT
        | VoiceAssistantFeature.SPEAKER
    )


@pytest.fixture
async def mock_voice_assistant_api_entry(mock_voice_assistant_entry) -> MockConfigEntry:
    """Set up an ESPHome entry with voice assistant."""
    return await mock_voice_assistant_entry(
        voice_assistant_feature_flags=VoiceAssistantFeature.VOICE_ASSISTANT
        | VoiceAssistantFeature.SPEAKER
        | VoiceAssistantFeature.API_AUDIO
    )


@pytest.fixture
async def mock_bluetooth_entry(
    hass: HomeAssistant,
    mock_client: APIClient,
):
    """Set up an ESPHome entry with bluetooth."""

    async def _mock_bluetooth_entry(
        bluetooth_proxy_feature_flags: BluetoothProxyFeature,
    ) -> MockESPHomeDevice:
        return await _mock_generic_device_entry(
            hass,
            mock_client,
            {"bluetooth_proxy_feature_flags": bluetooth_proxy_feature_flags},
            ([], []),
            [],
        )

    return _mock_bluetooth_entry


@pytest.fixture
async def mock_bluetooth_entry_with_raw_adv(mock_bluetooth_entry) -> MockESPHomeDevice:
    """Set up an ESPHome entry with bluetooth and raw advertisements."""
    return await mock_bluetooth_entry(
        bluetooth_proxy_feature_flags=BluetoothProxyFeature.PASSIVE_SCAN
        | BluetoothProxyFeature.ACTIVE_CONNECTIONS
        | BluetoothProxyFeature.REMOTE_CACHING
        | BluetoothProxyFeature.PAIRING
        | BluetoothProxyFeature.CACHE_CLEARING
        | BluetoothProxyFeature.RAW_ADVERTISEMENTS
    )


@pytest.fixture
async def mock_bluetooth_entry_with_legacy_adv(
    mock_bluetooth_entry,
) -> MockESPHomeDevice:
    """Set up an ESPHome entry with bluetooth with legacy advertisements."""
    return await mock_bluetooth_entry(
        bluetooth_proxy_feature_flags=BluetoothProxyFeature.PASSIVE_SCAN
        | BluetoothProxyFeature.ACTIVE_CONNECTIONS
        | BluetoothProxyFeature.REMOTE_CACHING
        | BluetoothProxyFeature.PAIRING
        | BluetoothProxyFeature.CACHE_CLEARING
    )


@pytest.fixture
async def mock_generic_device_entry(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
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
        mock_storage: bool = False,
    ) -> MockConfigEntry:
        return (
            await _mock_generic_device_entry(
                hass,
                mock_client,
                {},
                (entity_info, user_service),
                states,
                None,
                hass_storage if mock_storage else None,
            )
        ).entry

    return _mock_device_entry


@pytest.fixture
async def mock_esphome_device(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> Callable[
    [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
    Awaitable[MockESPHomeDevice],
]:
    """Set up an ESPHome entry and return the MockESPHomeDevice."""

    async def _mock_device(
        mock_client: APIClient,
        entity_info: list[EntityInfo] | None = None,
        user_service: list[UserService] | None = None,
        states: list[EntityState] | None = None,
        entry: MockConfigEntry | None = None,
        device_info: dict[str, Any] | None = None,
        mock_storage: bool = False,
    ) -> MockESPHomeDevice:
        return await _mock_generic_device_entry(
            hass,
            mock_client,
            device_info or {},
            (entity_info or [], user_service or []),
            states or [],
            entry,
            hass_storage if mock_storage else None,
        )

    return _mock_device
