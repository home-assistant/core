"""Fixtures for BSBLAN integration tests."""

from collections.abc import Generator
from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from bsblan import Device, HotWaterState, Info, Sensor, State, StaticState
import pytest

from homeassistant.components.bsblan.const import CONF_PASSKEY, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="BSBLAN Setup",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
        unique_id="00:80:41:19:69:90",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.bsblan.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_bsblan() -> Generator[MagicMock]:
    """Return a mocked BSBLAN client."""
    with (
        patch("homeassistant.components.bsblan.BSBLAN", autospec=True) as bsblan_mock,
        patch("homeassistant.components.bsblan.config_flow.BSBLAN", new=bsblan_mock),
    ):
        bsblan = bsblan_mock.return_value
        bsblan.info.return_value = Info.from_json(load_fixture("info.json", DOMAIN))
        bsblan.device.return_value = Device.from_json(
            load_fixture("device.json", DOMAIN)
        )
        bsblan.state.return_value = State.from_json(load_fixture("state.json", DOMAIN))
        bsblan.static_values.return_value = StaticState.from_json(
            load_fixture("static.json", DOMAIN)
        )
        bsblan.sensor.return_value = Sensor.from_json(
            load_fixture("sensor.json", DOMAIN)
        )
        bsblan.hot_water_state.return_value = HotWaterState.from_json(
            load_fixture("dhw_state.json", DOMAIN)
        )
        # mock get_temperature_unit property
        bsblan.get_temperature_unit = "°C"

        yield bsblan


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_bsblan: MagicMock
) -> MockConfigEntry:
    """Set up the bsblan integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


# ZeroconfServiceInfo fixtures for different discovery scenarios


@pytest.fixture
def zeroconf_discovery_info() -> ZeroconfServiceInfo:
    """Return zeroconf discovery info for a BSBLAN device with MAC address."""
    return ZeroconfServiceInfo(
        ip_address=ip_address("10.0.2.60"),
        ip_addresses=[ip_address("10.0.2.60")],
        name="BSB-LAN web service._http._tcp.local.",
        type="_http._tcp.local.",
        properties={"mac": "00:80:41:19:69:90"},
        port=80,
        hostname="BSB-LAN.local.",
    )


@pytest.fixture
def zeroconf_discovery_info_no_mac() -> Mock:
    """Return zeroconf discovery info for a BSBLAN device without MAC address."""
    discovery_info = Mock()
    discovery_info.ip_address = ip_address("10.0.2.60")
    discovery_info.ip_addresses = [ip_address("10.0.2.60")]
    discovery_info.name = "BSB-LAN web service._http._tcp.local."
    discovery_info.type = "_http._tcp.local."
    discovery_info.properties = {}  # No MAC in properties
    discovery_info.properties_raw = {}  # No MAC in properties_raw either
    discovery_info.port = 80
    discovery_info.hostname = "BSB-LAN.local."
    return discovery_info


@pytest.fixture
def zeroconf_discovery_info_different_ip() -> ZeroconfServiceInfo:
    """Return zeroconf discovery info for a BSBLAN device with different IP."""
    return ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        name="BSB-LAN web service._http._tcp.local.",
        type="_http._tcp.local.",
        properties={"mac": "00:80:41:19:69:90"},
        port=8080,
        hostname="BSB-LAN.local.",
    )


@pytest.fixture
def zeroconf_discovery_info_properties_raw() -> Mock:
    """Return zeroconf discovery info with MAC in properties_raw."""
    discovery_info = Mock()
    discovery_info.ip_address = ip_address("10.0.2.60")
    discovery_info.ip_addresses = [ip_address("10.0.2.60")]
    discovery_info.name = "BSB-LAN web service._http._tcp.local."
    discovery_info.type = "_http._tcp.local."
    discovery_info.properties = {}  # No MAC in properties
    discovery_info.properties_raw = {
        b"mac=00:80:41:19:69:90": b""
    }  # MAC in properties_raw
    discovery_info.port = 80
    discovery_info.hostname = "BSB-LAN.local."
    return discovery_info
