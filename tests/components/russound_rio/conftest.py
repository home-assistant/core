"""Test fixtures for Russound RIO integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from aiorussound.rio import Source
from aiorussound.rio.client import Controller, ZoneControlSurface
from aiorussound.util import controller_device_str, zone_device_str
import pytest

from homeassistant.components.russound_rio.const import DOMAIN

from .const import API_VERSION, HARDWARE_MAC, MOCK_SERIAL_CONFIG, MOCK_TCP_CONFIG, MODEL

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry():
    """Prevent setup."""
    with patch(
        "homeassistant.components.russound_rio.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a TCP config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_TCP_CONFIG,
        unique_id=HARDWARE_MAC,
        title=MODEL,
    )


@pytest.fixture
def mock_serial_config_entry() -> MockConfigEntry:
    """Mock a serial config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_SERIAL_CONFIG,
        unique_id=HARDWARE_MAC,
        title=MODEL,
    )


@pytest.fixture
def mock_russound_client() -> Generator[AsyncMock]:
    """Mock the Russound RIO client."""
    with (
        patch(
            "homeassistant.components.russound_rio.RussoundRIOClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.russound_rio.config_flow.RussoundRIOClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value

        def _init(handler):
            client.connection_handler = handler
            return client

        mock_client.side_effect = _init

        controller_zones = {
            int(controller_id): {
                int(zone_id): ZoneControlSurface.from_dict(zone)
                for zone_id, zone in v["zones"].items()
            }
            for controller_id, v in load_json_object_fixture("get_zones.json", DOMAIN)[
                "controllers"
            ].items()
        }
        client.sources = {
            int(k): Source.from_dict(v)
            for k, v in load_json_object_fixture("get_sources.json", DOMAIN).items()
        }
        client.state = load_json_object_fixture("get_state.json", DOMAIN)
        for controller_id, zones in controller_zones.items():
            for zone_id, zone in zones.items():
                zone.device_str = zone_device_str(controller_id, zone_id)
                zone.fetch_current_source = Mock(
                    side_effect=lambda current_source=zone.current_source: (
                        client.sources.get(int(current_source))
                    )
                )
                zone.volume_up = AsyncMock()
                zone.volume_down = AsyncMock()
                zone.set_volume = AsyncMock()
                zone.zone_on = AsyncMock()
                zone.zone_off = AsyncMock()
                zone.select_source = AsyncMock()
                zone.mute = AsyncMock()
                zone.unmute = AsyncMock()
                zone.toggle_mute = AsyncMock()
                zone.set_seek_time = AsyncMock()
                zone.set_balance = AsyncMock()
                zone.set_bass = AsyncMock()
                zone.set_treble = AsyncMock()
                zone.set_turn_on_volume = AsyncMock()
                zone.set_loudness = AsyncMock()
                zone.restore_preset = AsyncMock()
                zone.set_party_mode = AsyncMock()

        client.controllers = {
            1: Controller(
                1,
                MODEL,
                client,
                controller_device_str(1),
                HARDWARE_MAC,
                None,
                controller_zones[1],
            ),
            2: Controller(
                2,
                MODEL,
                client,
                controller_device_str(2),
                None,
                None,
                controller_zones[2],
            ),
        }
        client.is_connected = Mock(return_value=True)
        client.register_state_update_callbacks = AsyncMock()
        client.unregister_state_update_callbacks = Mock(return_value=True)
        client.rio_version = API_VERSION

        yield client


@pytest.fixture
def mock_tcp_handler() -> Generator[Mock]:
    """Mock the TCP connection handler."""
    with patch(
        "homeassistant.components.russound_rio.RussoundTcpConnectionHandler"
    ) as mock_handler:
        yield mock_handler


@pytest.fixture
def mock_serial_handler() -> Generator[Mock]:
    """Mock the serial connection handler."""
    with patch(
        "homeassistant.components.russound_rio.RussoundSerialConnectionHandler"
    ) as mock_handler:
        yield mock_handler
