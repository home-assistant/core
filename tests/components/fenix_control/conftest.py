"""Common fixtures for the FENIX Control tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyfenixcontrol import Device, Installation, PresetMode, Room
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.fenix_control.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

USER_ID = "8f1c2d3e-4a5b-4c6d-8e9f-0a1b2c3d4e5f"
EMAIL = "user@example.com"
PASSWORD = "test-password"
INSTALLATION_ID = "AABB1122CCDD"
ROOM_ID = "aaaabbbb-cccc-dddd-eeee-111122223333"
DEVICE_ID = "AA11BB22CC00"

ROOM = Room(id=ROOM_ID, name="Living room", device_ids=(DEVICE_ID,))
INSTALLATION = Installation(id=INSTALLATION_ID, name="Home", rooms=(ROOM,), raw={})
DEVICE = Device(
    id=DEVICE_ID,
    name="Living room",
    installation_id=INSTALLATION_ID,
    installation_name="Home",
    room_id=ROOM_ID,
    software_version="v01.06.01",
    model="P07542",
    target_temperature=22.5,
    room_temperature=19.2,
    floor_temperature=20.0,
    holiday_target_temperature=16.0,
    preset_mode=int(PresetMode.MANUAL),
    hvac_state=1,
    holiday_start=None,
    holiday_end=None,
    holiday_mode=0,
    active_holiday_mode=0,
    raw={},
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fenix_control.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=EMAIL,
        data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD},
        unique_id=USER_ID,
        entry_id="01JKRA6QKPBE00ZZ9BKWDB3CTB",
    )


@pytest.fixture
def mock_fenix_client() -> Generator[MagicMock]:
    """Return a mocked FenixControlClient used by setup and the config flow."""
    with (
        patch(
            "homeassistant.components.fenix_control.FenixControlClient",
            autospec=True,
        ) as mock_client_class,
        patch(
            "homeassistant.components.fenix_control.config_flow.FenixControlClient",
            new=mock_client_class,
        ),
        patch("homeassistant.components.fenix_control.PasswordAuth"),
        patch("homeassistant.components.fenix_control.config_flow.PasswordAuth"),
    ):
        client = mock_client_class.return_value
        client.get_user_id.return_value = USER_ID
        client.get_installations.return_value = [INSTALLATION]
        client.get_devices.return_value = [DEVICE]
        yield client


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.CLIMATE]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fenix_client: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the FENIX Control integration for testing."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.fenix_control._PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_config_entry
