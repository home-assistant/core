"""Test fixtures for Russound RIO integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from aiorussound import Controller, RussoundTcpConnectionHandler, Source
from aiorussound.rio import ZoneControlSurface
from aiorussound.util import controller_device_str, zone_device_str
import pytest

from homeassistant.components.russound_rio.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import HARDWARE_MAC, HOST, MOCK_CONFIG, MODEL, PORT

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry():
    """Prevent setup."""
    with patch(
        "homeassistant.components.russound_rio.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a Russound RIO config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=HARDWARE_MAC, title=MODEL
    )


@pytest.fixture
def mock_russound_client() -> Generator[AsyncMock]:
    """Mock the Russound RIO client."""
    with (
        patch(
            "homeassistant.components.russound_rio.RussoundClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.russound_rio.config_flow.RussoundClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        zones = {
            int(k): ZoneControlSurface.from_dict(v)
            for k, v in load_json_object_fixture("get_zones.json", DOMAIN).items()
        }
        client.sources = {
            int(k): Source.from_dict(v)
            for k, v in load_json_object_fixture("get_sources.json", DOMAIN).items()
        }
        for k, v in zones.items():
            v.device_str = zone_device_str(1, k)
            v.fetch_current_source = Mock(
                side_effect=lambda current_source=v.current_source: client.sources.get(
                    int(current_source)
                )
            )

        client.controllers = {
            1: Controller(
                1, "MCA-C5", client, controller_device_str(1), HARDWARE_MAC, None, zones
            )
        }
        client.connection_handler = RussoundTcpConnectionHandler(HOST, PORT)
        client.is_connected = Mock(return_value=True)
        client.unregister_state_update_callbacks.return_value = True
        yield client
