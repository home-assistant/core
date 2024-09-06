"""GeniusHub tests configuration."""

from collections.abc import Generator
from unittest.mock import patch

from geniushubclient import GeniusDevice, GeniusZone
import pytest

from homeassistant.components.geniushub.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME

from tests.common import MockConfigEntry, load_json_array_fixture
from tests.components.smhi.common import AsyncMock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.geniushub.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_geniushub_client() -> Generator[AsyncMock]:
    """Mock a GeniusHub client."""
    with patch(
        "homeassistant.components.geniushub.config_flow.GeniusService",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.request.return_value = {
            "data": {
                "UID": "aa:bb:cc:dd:ee:ff",
            }
        }
        yield client


@pytest.fixture
def mock_geniushub_cloud() -> Generator[MagicMock]:
    """Mock a GeniusHub."""
    with patch(
        "homeassistant.components.geniushub.GeniusHub",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        zones = load_json_array_fixture("zones_cloud_test_data.json", DOMAIN)
        genius_zones = [GeniusZone(z["id"], z, client) for z in zones]
        client.zone_objs = genius_zones
        client._zones = genius_zones
        devices = load_json_array_fixture("devices_cloud_test_data.json", DOMAIN)
        genius_devices = [GeniusDevice(d["id"], d, client) for d in devices]
        client.device_objs = genius_devices
        client._devices = genius_devices
        client.api_version = 1
        yield client


@pytest.fixture
def mock_local_config_entry() -> MockConfigEntry:
    """Mock a local config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="aa:bb:cc:dd:ee:ff",
        data={
            CONF_HOST: "10.0.0.131",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )


@pytest.fixture
def mock_cloud_config_entry() -> MockConfigEntry:
    """Mock a cloud config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Genius hub",
        data={
            CONF_TOKEN: "abcdef",
        },
        entry_id="01J71MQF0EC62D620DGYNG2R8H",
    )
