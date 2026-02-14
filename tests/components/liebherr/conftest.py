"""Common fixtures for the liebherr tests."""

from collections.abc import Generator
import copy
from unittest.mock import AsyncMock, MagicMock, patch

from pyliebherrhomeapi import (
    Device,
    DeviceState,
    DeviceType,
    TemperatureControl,
    TemperatureUnit,
    ToggleControl,
    ZonePosition,
)
import pytest

from homeassistant.components.liebherr.const import DOMAIN
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# Complete multi-zone device for comprehensive testing
MOCK_DEVICE = Device(
    device_id="test_device_id",
    nickname="Test Fridge",
    device_type=DeviceType.COMBI,
    device_name="CBNes1234",
)

MOCK_DEVICE_STATE = DeviceState(
    device=MOCK_DEVICE,
    controls=[
        TemperatureControl(
            zone_id=1,
            zone_position=ZonePosition.TOP,
            name="Fridge",
            type="fridge",
            value=5,
            target=4,
            min=2,
            max=8,
            unit=TemperatureUnit.CELSIUS,
        ),
        TemperatureControl(
            zone_id=2,
            zone_position=ZonePosition.BOTTOM,
            name="Freezer",
            type="freezer",
            value=-18,
            target=-18,
            min=-24,
            max=-16,
            unit=TemperatureUnit.CELSIUS,
        ),
        ToggleControl(
            name="supercool",
            type="ToggleControl",
            zone_id=1,
            zone_position=ZonePosition.TOP,
            value=False,
        ),
        ToggleControl(
            name="superfrost",
            type="ToggleControl",
            zone_id=2,
            zone_position=ZonePosition.BOTTOM,
            value=True,
        ),
        ToggleControl(
            name="partymode",
            type="ToggleControl",
            zone_id=None,
            zone_position=None,
            value=False,
        ),
        ToggleControl(
            name="nightmode",
            type="ToggleControl",
            zone_id=None,
            zone_position=None,
            value=True,
        ),
    ],
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.liebherr.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        title="Liebherr",
    )


@pytest.fixture
def mock_liebherr_client() -> Generator[MagicMock]:
    """Return a mocked Liebherr client."""
    with (
        patch(
            "homeassistant.components.liebherr.LiebherrClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.liebherr.config_flow.LiebherrClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_devices.return_value = [MOCK_DEVICE]
        # Return a fresh copy each call so mutations don't leak between calls.
        client.get_device_state.side_effect = lambda *a, **kw: copy.deepcopy(
            MOCK_DEVICE_STATE
        )
        client.set_temperature = AsyncMock()
        client.set_supercool = AsyncMock()
        client.set_superfrost = AsyncMock()
        client.set_party_mode = AsyncMock()
        client.set_night_mode = AsyncMock()
        yield client


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Liebherr integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.liebherr.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
