"""Test fixtures for Bravia TV."""

from collections.abc import Generator
import copy
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.braviatv.const import CONF_USE_PSK, DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN

BRAVIA_SYSTEM_INFO = {
    "product": "TV",
    "region": "XEU",
    "language": "pol",
    "model": "TV-Model",
    "serial": "serial_number",
    "macAddr": "AA:BB:CC:DD:EE:FF",
    "name": "BRAVIA",
    "generation": "5.2.0",
    "area": "POL",
    "cid": "very_unique_string",
}

BRAVIA_INPUTS = [
    {
        "uri": "extInput:hdmi?port=1",
        "title": "HDMI 1",
        "connection": True,
        "label": "",
        "icon": "meta:hdmi",
    },
    {
        "uri": "extInput:hdmi?port=2",
        "title": "HDMI 2",
        "connection": False,
        "label": "",
        "icon": "meta:hdmi",
    },
    {
        "uri": "extInput:component?port=1",
        "title": "AV/Component",
        "connection": False,
        "label": "",
        "icon": "meta:component",
    },
]

BRAVIA_APPS = [
    {
        "title": "YouTube",
        "uri": "com.sony.dtv.com.google.android.youtube.tv",
        "icon": "http://bravia-host/youtube.png",
    },
    {
        "title": "Netflix",
        "uri": "com.sony.dtv.com.netflix.ninja",
        "icon": "http://bravia-host/netflix.png",
    },
    {
        "title": "Settings",
        "uri": "com.sony.dtv.com.android.tv.settings",
        "icon": "",
    },
]

BRAVIA_CHANNELS = [
    {
        "uri": "tv:dvbt?trip=1.2.3&srvName=TVP1",
        "title": "TVP 1",
        "dispNum": "001",
        "index": 0,
        "programMediaType": "tv",
    },
    {
        "uri": "tv:dvbt?trip=1.2.4&srvName=TVP2",
        "title": "TVP 2",
        "dispNum": "002",
        "index": 1,
        "programMediaType": "tv",
    },
    {
        "uri": "tv:dvbt?trip=1.2.5&srvName=TVN",
        "title": "TVN",
        "dispNum": "003",
        "index": 2,
        "programMediaType": "tv",
    },
]

BRAVIA_VOLUME_INFO = {"volume": 25, "mute": False, "target": "speaker"}

BRAVIA_PLAYING_INFO = {
    "uri": "extInput:hdmi?port=1",
    "source": "extInput:hdmi",
    "title": "HDMI 1",
}

BRAVIA_COMMAND_LIST = {
    "Power": "AAAAAQAAAAEAAAAVAw==",
    "Num1": "AAAAAQAAAAEAAAAAAw==",
    "VolumeUp": "AAAAAQAAAAEAAAASAw==",
}


@pytest.fixture(autouse=True)
def silent_ssdp_scanner() -> Generator[None]:
    """Start SSDP component and get Scanner, prevent actual SSDP traffic."""
    with (
        patch("homeassistant.components.ssdp.Scanner._async_start_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner._async_stop_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner.async_scan"),
        patch(
            "homeassistant.components.ssdp.Server._async_start_upnp_servers",
        ),
        patch(
            "homeassistant.components.ssdp.Server._async_stop_upnp_servers",
        ),
    ):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.braviatv.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="BRAVIA TV-Model",
        unique_id="very_unique_string",
        entry_id="3bd2acb0e4f0476d40865546d0d91921",
        minor_version=2,
        data={
            CONF_HOST: "bravia-host",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_PIN: "12345qwerty",
            CONF_USE_PSK: True,
        },
    )


@pytest.fixture
def mock_braviatv() -> Generator[AsyncMock]:
    """Mock the BraviaClient class."""
    with (
        patch(
            "homeassistant.components.braviatv.BraviaClient", autospec=True
        ) as mock_class,
        patch(
            "homeassistant.components.braviatv.config_flow.BraviaClient",
            new=mock_class,
        ),
    ):
        yield mock_class


@pytest.fixture
def mock_braviatv_client(mock_braviatv: AsyncMock) -> AsyncMock:
    """Mock a BraviaClient instance."""
    client = mock_braviatv.return_value
    client.mac = "AA:BB:CC:DD:EE:FF"
    client.get_app_list.return_value = copy.deepcopy(BRAVIA_APPS)
    client.get_command_list.return_value = copy.deepcopy(BRAVIA_COMMAND_LIST)
    client.get_content_list_all.return_value = copy.deepcopy(BRAVIA_CHANNELS)
    client.get_external_status.return_value = copy.deepcopy(BRAVIA_INPUTS)
    client.get_playing_info.return_value = copy.deepcopy(BRAVIA_PLAYING_INFO)
    client.get_power_status.return_value = "active"
    client.get_system_info.return_value = copy.deepcopy(BRAVIA_SYSTEM_INFO)
    client.get_volume_info.return_value = copy.deepcopy(BRAVIA_VOLUME_INFO)
    client.send_command.return_value = True

    return client
