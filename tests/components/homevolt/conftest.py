"""Common fixtures for the Homevolt tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from homevolt import Device, DeviceMetadata, Sensor, SensorType
import pytest

from homeassistant.components.homevolt.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.homevolt.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Homevolt",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "test-password",
        },
        unique_id="40580137858664",
    )


@pytest.fixture
def mock_homevolt_client() -> Generator[MagicMock]:
    """Return a mocked Homevolt client."""
    with (
        patch(
            "homeassistant.components.homevolt.Homevolt",
            autospec=True,
        ) as homevolt_mock,
        patch(
            "homeassistant.components.homevolt.config_flow.Homevolt",
            new=homevolt_mock,
        ),
    ):
        client = homevolt_mock.return_value
        client.base_url = "http://127.0.0.1"
        client.update_info = AsyncMock()

        # Create a mock Device with sensors
        device = MagicMock(spec=Device)
        device.device_id = "40580137858664"
        device.sensors = {
            "L1 Voltage": Sensor(
                value=234.5,
                type=SensorType.VOLTAGE,
                device_identifier="ems_40580137858664",
                slug="l1_voltage",
            ),
            "Battery State of Charge": Sensor(
                value=80.6,
                type=SensorType.PERCENTAGE,
                device_identifier="ems_40580137858664",
                slug="battery_state_of_charge",
            ),
            "Power": Sensor(
                value=-12,
                type=SensorType.POWER,
                device_identifier="ems_40580137858664",
                slug="power",
            ),
        }
        device.device_metadata = {
            "ems_40580137858664": DeviceMetadata(
                name="Homevolt EMS",
                model="EMS-1000",
            ),
        }
        client.get_device.return_value = device

        yield client


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to test."""
    return [Platform.SENSOR]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homevolt_client: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Homevolt integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.homevolt.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
