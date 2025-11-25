"""Configuration for Velux tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyvlx.lightening_device import LighteningDevice
from pyvlx.opening_device import Blind, Window

from homeassistant.components.velux import DOMAIN
from homeassistant.components.velux.scene import PyVLXScene as Scene
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


# Fixtures for the config flow tests
@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.velux.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry (unified fixture for all tests)."""
    return MockConfigEntry(
        entry_id="test_entry_id",
        domain=DOMAIN,
        title="127.0.0.1",
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "NotAStrongPassword",
        },
    )


@pytest.fixture
def mock_discovered_config_entry() -> MockConfigEntry:
    """Return the user config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="127.0.0.1",
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "NotAStrongPassword",
            CONF_MAC: "64:61:84:00:ab:cd",
        },
        unique_id="VELUX_KLF_ABCD",
    )


# various types of fixtures for specific node types
# first the window
@pytest.fixture
def mock_window() -> AsyncMock:
    """Create a mock Velux window with a rain sensor."""
    window = AsyncMock(spec=Window, autospec=True)
    window.name = "Test Window"
    window.rain_sensor = True
    window.serial_number = "123456789"
    window.get_limitation.return_value = MagicMock(min_value=0)
    window.is_opening = False
    window.is_closing = False
    window.position = MagicMock(position_percent=30, closed=False)
    return window


# a blind
@pytest.fixture
def mock_blind() -> AsyncMock:
    """Create a mock Velux blind (cover with tilt)."""
    blind = AsyncMock(spec=Blind, autospec=True)
    blind.name = "Test Blind"
    blind.serial_number = "4711"
    # Standard cover position (used by current_cover_position)
    blind.position = MagicMock(position_percent=40, closed=False)
    blind.is_opening = False
    blind.is_closing = False
    # Orientation/tilt-related attributes and methods
    blind.orientation = MagicMock(position_percent=25)
    blind.open_orientation = AsyncMock()
    blind.close_orientation = AsyncMock()
    blind.stop_orientation = AsyncMock()
    blind.set_orientation = AsyncMock()
    return blind


# a light
@pytest.fixture
def mock_light() -> AsyncMock:
    """Create a mock Velux light."""
    light = AsyncMock(spec=LighteningDevice, autospec=True)
    light.name = "Test Light"
    light.serial_number = "0815"
    light.intensity = MagicMock()
    return light


# fixture to create all other cover types via parameterization
@pytest.fixture
def mock_cover_type(request: pytest.FixtureRequest) -> AsyncMock:
    """Create a mock Velux cover of specified type."""
    cover = AsyncMock(spec=request.param, autospec=True)
    cover.name = f"Test {request.param.__name__}"
    cover.serial_number = f"serial_{request.param.__name__}"
    cover.is_opening = False
    cover.is_closing = False
    cover.position = MagicMock(position_percent=30, closed=False)
    return cover


@pytest.fixture
def mock_pyvlx(
    mock_scene: AsyncMock,
    mock_light: AsyncMock,
    mock_window: AsyncMock,
    mock_blind: AsyncMock,
    request: pytest.FixtureRequest,
) -> Generator[MagicMock]:
    """Create the library mock and patch PyVLX in both component and config_flow.

    Tests can parameterize this fixture with the name of a node fixture to include
    (e.g., "mock_window", "mock_blind", "mock_light", or "mock_cover_type").
    If no parameter is provided, an empty node list is used.
    """

    pyvlx = MagicMock()

    if hasattr(request, "param"):
        pyvlx.nodes = [request.getfixturevalue(request.param)]
    else:
        pyvlx.nodes = [mock_light, mock_blind, mock_window, mock_cover_type]

    pyvlx.scenes = [mock_scene]

    # Async methods invoked by the integration/config flow
    pyvlx.load_scenes = AsyncMock()
    pyvlx.load_nodes = AsyncMock()
    pyvlx.connect = AsyncMock()
    pyvlx.disconnect = AsyncMock()

    with (
        patch("homeassistant.components.velux.PyVLX", return_value=pyvlx),
        patch("homeassistant.components.velux.config_flow.PyVLX", return_value=pyvlx),
    ):
        yield pyvlx


@pytest.fixture
def mock_scene() -> AsyncMock:
    """Create a mock Velux scene."""
    scene = AsyncMock(spec=Scene, autospec=True)
    scene.name = "Test Scene"
    scene.scene_id = "1234"
    scene.scene = AsyncMock()
    return scene


# Fixture to set up the integration for testing, needs platform fixture, to be defined in each test file
@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyvlx: AsyncMock,
    platform: Platform,
) -> None:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.velux.PLATFORMS", [platform]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
