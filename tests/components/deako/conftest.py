"""deako session fixtures."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.deako.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class MockDeakoDevices:
    """Mock Deako devices container."""

    devices: dict[str, dict] = {
        "uuid1": {  # non-dimmable
            "name": "kitchen",
            "state": {
                "power": False,
            },
        },
        "uuid2": {  # dimmable
            "name": "living_room",
            "state": {
                "power": True,
                "dim": 50,
                "convertedDim": 127,
            },
        },
        "uuid3": {  # dimmable
            "name": "master_bedroom",
            "state": {
                "power": True,
                "dim": 0,
                "convertedDim": 0,
            },
        },
        "uuid4": {  # dimmable
            "name": "master_bathroom",
            "state": {
                "power": True,
                "dim": 100,
                "convertedDim": 255,
            },
        },
    }

    def get_names(self) -> list[(str, str)]:
        """Return list of tuples with name and uuid."""
        return [(self.devices[uuid]["name"], uuid) for uuid in self.devices]

    def get_name(self, uuid: str) -> str:
        """Get the name of a mock device by uuid."""
        return self.devices[uuid]["name"]

    def get_state(self, uuid: str) -> dict:
        """Get the state of a mock device by uuid."""
        return self.devices[uuid]["state"]


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id="aabbccddeeff",
    )


@pytest.fixture(autouse=True)
def deako_mock_async_zeroconf(mock_async_zeroconf):
    """Auto mock zeroconf."""


@pytest.fixture(name="pydeako_deako_mock", autouse=True)
def pydeako_deako_mock():
    """Mock pydeako deako client."""
    with patch("homeassistant.components.deako.Deako", autospec=True) as mock:
        yield mock


@pytest.fixture(name="pydeako_discoverer_mock", autouse=True)
def pydeako_discoverer_mock():
    """Mock pydeako discovery client."""
    with patch("homeassistant.components.deako.DeakoDiscoverer", autospec=True) as mock:
        yield mock


@pytest.fixture(name="mock_devices")
def mock_devices() -> MockDeakoDevices:
    """Mock deako devices."""
    return MockDeakoDevices()


@pytest.fixture(name="mock_deako_devices")
def mock_deako_devices(pydeako_deako_mock: MagicMock, mock_devices: MockDeakoDevices):
    """Mock pydeako client to return mock deako devices."""
    pydeako_deako_mock.return_value.get_devices.return_value = mock_devices.devices

    pydeako_deako_mock.return_value.get_name.side_effect = mock_devices.get_name
    pydeako_deako_mock.return_value.get_state.side_effect = mock_devices.get_state


@pytest.fixture(name="init_integration")
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    pydeako_deako_mock: MagicMock,
) -> MockConfigEntry:
    """Set up the Deako integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.data[DOMAIN][mock_config_entry.entry_id] = pydeako_deako_mock
    return mock_config_entry
