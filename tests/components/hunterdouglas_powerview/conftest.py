"""Common fixtures for Hunter Douglas Powerview tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from aiopvapi.resources.shade import ShadePosition
import pytest

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN

from tests.common import load_json_object_fixture, load_json_value_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hunterdouglas_powerview.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_hunterdouglas_hub(
    device_json: str,
    home_json: str,
    firmware_json: str,
    rooms_json: str,
    scenes_json: str,
    shades_json: str,
) -> Generator[MagicMock, None, None]:
    """Return a mocked Powerview Hub with all data populated."""
    with (
        patch(
            "homeassistant.components.hunterdouglas_powerview.Hub.request_raw_data",
            return_value=load_json_object_fixture(device_json, DOMAIN),
        ),
        patch(
            "homeassistant.components.hunterdouglas_powerview.Hub.request_home_data",
            return_value=load_json_object_fixture(home_json, DOMAIN),
        ),
        patch(
            "homeassistant.components.hunterdouglas_powerview.Hub.request_raw_firmware",
            return_value=load_json_object_fixture(firmware_json, DOMAIN),
        ),
        patch(
            "homeassistant.components.hunterdouglas_powerview.Rooms.get_resources",
            return_value=load_json_value_fixture(rooms_json, DOMAIN),
        ),
        patch(
            "homeassistant.components.hunterdouglas_powerview.Scenes.get_resources",
            return_value=load_json_value_fixture(scenes_json, DOMAIN),
        ),
        patch(
            "homeassistant.components.hunterdouglas_powerview.Shades.get_resources",
            return_value=load_json_value_fixture(shades_json, DOMAIN),
        ),
        patch(
            "homeassistant.components.hunterdouglas_powerview.cover.BaseShade.refresh",
        ),
        patch(
            "homeassistant.components.hunterdouglas_powerview.cover.BaseShade.current_position",
            new_callable=PropertyMock,
            return_value=ShadePosition(primary=0, secondary=0, tilt=0, velocity=0),
        ),
    ):
        yield


@pytest.fixture
def device_json(api_version: int) -> str:
    """Return the request_raw_data fixture for a specific device."""
    if api_version == 1:
        return "gen1/userdata.json"
    if api_version == 2:
        return "gen2/userdata.json"
    if api_version == 3:
        return "gen3/gateway/primary.json"
    # Add more conditions for different api_versions if needed
    raise ValueError(f"Unsupported api_version: {api_version}")


@pytest.fixture
def home_json(api_version: int) -> str:
    """Return the request_home_data fixture for a specific device."""
    if api_version == 1:
        return "gen1/userdata.json"
    if api_version == 2:
        return "gen2/userdata.json"
    if api_version == 3:
        return "gen3/home/home.json"
    # Add more conditions for different api_versions if needed
    raise ValueError(f"Unsupported api_version: {api_version}")


@pytest.fixture
def firmware_json(api_version: int) -> str:
    """Return the request_raw_firmware fixture for a specific device."""
    if api_version == 1:
        return "gen1/fwversion.json"
    if api_version == 2:
        return "gen2/fwversion.json"
    if api_version == 3:
        return "gen3/gateway/info.json"
    # Add more conditions for different api_versions if needed
    raise ValueError(f"Unsupported api_version: {api_version}")


@pytest.fixture
def rooms_json(api_version: int) -> str:
    """Return the get_resources fixture for a specific device."""
    if api_version == 1:
        return "gen2/rooms.json"
    if api_version == 2:
        return "gen2/rooms.json"
    if api_version == 3:
        return "gen3/home/rooms.json"
    # Add more conditions for different api_versions if needed
    raise ValueError(f"Unsupported api_version: {api_version}")


@pytest.fixture
def scenes_json(api_version: int) -> str:
    """Return the get_resources fixture for a specific device."""
    if api_version == 1:
        return "gen2/scenes.json"
    if api_version == 2:
        return "gen2/scenes.json"
    if api_version == 3:
        return "gen3/home/scenes.json"
    # Add more conditions for different api_versions if needed
    raise ValueError(f"Unsupported api_version: {api_version}")


@pytest.fixture
def shades_json(api_version: int) -> str:
    """Return the get_resources fixture for a specific device."""
    if api_version == 1:
        return "gen2/shades.json"
    if api_version == 2:
        return "gen2/shades.json"
    if api_version == 3:
        return "gen3/home/shades.json"
    # Add more conditions for different api_versions if needed
    raise ValueError(f"Unsupported api_version: {api_version}")
