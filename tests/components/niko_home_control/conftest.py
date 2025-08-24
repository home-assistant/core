"""niko_home_control integration tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from nhc.cover import NHCCover
from nhc.light import NHCLight
import pytest

from homeassistant.components.niko_home_control.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override integration setup."""
    with patch(
        "homeassistant.components.niko_home_control.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def light() -> NHCLight:
    """Return a light mock."""
    mock = AsyncMock(spec=NHCLight)
    mock.id = 1
    mock.type = 1
    mock.is_dimmable = False
    mock.name = "light"
    mock.suggested_area = "room"
    mock.state = 100
    return mock


@pytest.fixture
def dimmable_light() -> NHCLight:
    """Return a dimmable light mock."""
    mock = AsyncMock(spec=NHCLight)
    mock.id = 2
    mock.type = 2
    mock.is_dimmable = True
    mock.name = "dimmable light"
    mock.suggested_area = "room"
    mock.state = 255
    return mock


@pytest.fixture
def cover() -> NHCCover:
    """Return a cover mock."""
    mock = AsyncMock(spec=NHCCover)
    mock.id = 3
    mock.type = 4
    mock.name = "cover"
    mock.suggested_area = "room"
    mock.state = 100
    return mock


@pytest.fixture
def mock_niko_home_control_connection(
    light: NHCLight, dimmable_light: NHCLight, cover: NHCCover
) -> Generator[AsyncMock]:
    """Mock a NHC client."""
    with (
        patch(
            "homeassistant.components.niko_home_control.NHCController",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.niko_home_control.config_flow.NHCController",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.lights = [light, dimmable_light]
        client.covers = [cover]
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Niko Home Control",
        data={CONF_HOST: "192.168.0.123"},
        entry_id="01JFN93M7KRA38V5AMPCJ2JYYV",
    )
