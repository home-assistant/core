"""Test fixtures for mqtt component."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from random import getrandbits
from typing import Any
from unittest.mock import DEFAULT, AsyncMock, MagicMock, patch

import pytest

from homeassistant.components import mqtt
from homeassistant.components.mqtt.models import MessageCallbackType, ReceiveMessage
from homeassistant.components.mqtt.util import EnsureJobAfterCooldown
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, callback

from tests.common import MockConfigEntry
from tests.typing import MqttMockPahoClient

ENTRY_DEFAULT_BIRTH_MESSAGE = {
    mqtt.CONF_BROKER: "mock-broker",
    mqtt.CONF_BIRTH_MESSAGE: {
        mqtt.ATTR_TOPIC: "homeassistant/status",
        mqtt.ATTR_PAYLOAD: "online",
        mqtt.ATTR_QOS: 0,
        mqtt.ATTR_RETAIN: False,
    },
}


@pytest.fixture(autouse=True)
def patch_hass_config(mock_hass_config: None) -> None:
    """Patch configuration.yaml."""


@pytest.fixture
def temp_dir_prefix() -> str:
    """Set an alternate temp dir prefix."""
    return "test"


@pytest.fixture
def mock_temp_dir(temp_dir_prefix: str) -> Generator[str]:
    """Mock the certificate temp directory."""
    with patch(
        # Patch temp dir name to avoid tests fail running in parallel
        "homeassistant.components.mqtt.util.TEMP_DIR_NAME",
        f"home-assistant-mqtt-{temp_dir_prefix}-{getrandbits(10):03x}",
    ) as mocked_temp_dir:
        yield mocked_temp_dir


@pytest.fixture
def mock_debouncer(hass: HomeAssistant) -> Generator[asyncio.Event]:
    """Mock EnsureJobAfterCooldown.

    Returns an asyncio.Event that allows to await the debouncer task to be finished.
    """
    task_done = asyncio.Event()

    class MockDeboncer(EnsureJobAfterCooldown):
        """Mock the MQTT client (un)subscribe debouncer."""

        async def _async_job(self) -> None:
            """Execute after a cooldown period."""
            await super()._async_job()
            task_done.set()

    # We mock the import of EnsureJobAfterCooldown in client.py
    with patch(
        "homeassistant.components.mqtt.client.EnsureJobAfterCooldown", MockDeboncer
    ):
        yield task_done


@pytest.fixture
async def setup_with_birth_msg_client_mock(
    hass: HomeAssistant,
    mqtt_config_entry_data: dict[str, Any] | None,
    mqtt_client_mock: MqttMockPahoClient,
) -> AsyncGenerator[MqttMockPahoClient]:
    """Test sending birth message."""
    birth = asyncio.Event()
    with (
        patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0),
        patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.0),
        patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 0.0),
    ):
        entry = MockConfigEntry(
            domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"}
        )
        entry.add_to_hass(hass)
        hass.config.components.add(mqtt.DOMAIN)
        assert await hass.config_entries.async_setup(entry.entry_id)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)

        @callback
        def wait_birth(msg: ReceiveMessage) -> None:
            """Handle birth message."""
            birth.set()

        await mqtt.async_subscribe(hass, "homeassistant/status", wait_birth)
        await hass.async_block_till_done()
        await birth.wait()
        yield mqtt_client_mock


@pytest.fixture
def recorded_calls() -> list[ReceiveMessage]:
    """Fixture to hold recorded calls."""
    return []


@pytest.fixture
def record_calls(recorded_calls: list[ReceiveMessage]) -> MessageCallbackType:
    """Fixture to record calls."""

    @callback
    def record_calls(msg: ReceiveMessage) -> None:
        """Record calls."""
        recorded_calls.append(msg)

    return record_calls


@pytest.fixture(name="supervisor")
def supervisor_fixture() -> Generator[MagicMock]:
    """Mock Supervisor."""
    with patch(
        "homeassistant.components.mqtt.config_flow.is_hassio", return_value=True
    ) as is_hassio:
        yield is_hassio


@pytest.fixture(name="discovery_info")
def discovery_info_fixture() -> Any:
    """Return the discovery info from the supervisor."""
    return DEFAULT


@pytest.fixture(name="get_addon_discovery_info", autouse=True)
def get_addon_discovery_info_fixture(discovery_info: Any) -> Generator[AsyncMock]:
    """Mock get add-on discovery info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_discovery_info",
        return_value=discovery_info,
    ) as get_addon_discovery_info:
        yield get_addon_discovery_info


@pytest.fixture(name="addon_setup_time", autouse=True)
def addon_setup_time_fixture() -> Generator[int]:
    """Mock add-on setup sleep time."""
    with patch(
        "homeassistant.components.mqtt.config_flow.ADDON_SETUP_TIMEOUT", new=0
    ) as addon_setup_time:
        yield addon_setup_time


@pytest.fixture(name="addon_store_info")
def addon_store_info_fixture() -> Generator[AsyncMock]:
    """Mock Supervisor add-on store info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_store_info"
    ) as addon_store_info:
        addon_store_info.return_value = {
            "available": False,
            "installed": None,
            "state": None,
            "version": "1.0.0",
        }
        yield addon_store_info


@pytest.fixture(name="addon_info")
def addon_info_fixture() -> Generator[AsyncMock]:
    """Mock Supervisor add-on info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_info",
    ) as addon_info:
        addon_info.return_value = {
            "available": False,
            "hostname": None,
            "options": {},
            "state": None,
            "update_available": False,
            "version": None,
        }
        yield addon_info


@pytest.fixture(name="addon_not_installed")
def addon_not_installed_fixture(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> AsyncMock:
    """Mock add-on not installed."""
    addon_store_info.return_value["available"] = True
    return addon_info


@pytest.fixture(name="addon_installed")
def addon_installed_fixture(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> AsyncMock:
    """Mock add-on already installed but not running."""
    addon_store_info.return_value = {
        "available": True,
        "installed": "1.0.0",
        "state": "stopped",
        "version": "1.0.0",
    }
    addon_info.return_value["available"] = True
    addon_info.return_value["hostname"] = "core-matter-server"
    addon_info.return_value["state"] = "stopped"
    addon_info.return_value["version"] = "1.0.0"
    return addon_info


@pytest.fixture(name="addon_running")
def addon_running_fixture(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> AsyncMock:
    """Mock add-on already running."""
    addon_store_info.return_value = {
        "available": True,
        "installed": "1.0.0",
        "state": "started",
        "version": "1.0.0",
    }
    addon_info.return_value["available"] = True
    addon_info.return_value["hostname"] = "core-mosquitto"
    addon_info.return_value["state"] = "started"
    addon_info.return_value["version"] = "1.0.0"
    return addon_info


@pytest.fixture(name="install_addon")
def install_addon_fixture(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> Generator[AsyncMock]:
    """Mock install add-on."""

    async def install_addon_side_effect(hass: HomeAssistant, slug: str) -> None:
        """Mock install add-on."""
        addon_store_info.return_value = {
            "available": True,
            "installed": "1.0.0",
            "state": "stopped",
            "version": "1.0.0",
        }
        addon_info.return_value["available"] = True
        addon_info.return_value["state"] = "stopped"
        addon_info.return_value["version"] = "1.0.0"

    with patch(
        "homeassistant.components.hassio.addon_manager.async_install_addon"
    ) as install_addon:
        install_addon.side_effect = install_addon_side_effect
        yield install_addon


@pytest.fixture(name="start_addon")
def start_addon_fixture() -> Generator[AsyncMock]:
    """Mock start add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_start_addon"
    ) as start_addon:
        yield start_addon
