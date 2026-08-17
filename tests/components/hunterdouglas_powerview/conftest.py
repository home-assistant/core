"""Common fixtures for Hunter Douglas Powerview tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, PropertyMock, patch

from aiopvapi.resources.shade import ShadePosition
import pytest

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN

from tests.common import load_json_value_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
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
    room_json: str,
    scene_json: str,
    scenemember_json: str,
    shade_json: str,
    automation_json: str,
) -> Generator[None]:
    """Return a mocked Powerview Hub with all data populated."""
    with (
        patch(
            "homeassistant.components.hunterdouglas_powerview.cover.BaseShade.refresh",
        ),
        patch(
            "homeassistant.components.hunterdouglas_powerview.cover.BaseShade.current_position",
            new_callable=PropertyMock,
            return_value=ShadePosition(primary=0, secondary=0, tilt=0, velocity=0),
        ),
        patch("aiopvapi.hub.Hub.request_raw_data", return_value=device_json),
        patch("aiopvapi.hub.Hub.request_home_data", return_value=home_json),
        patch("aiopvapi.hub.Hub.request_raw_firmware", return_value=firmware_json),
        patch("aiopvapi.shades.Shades.get_resources", return_value=shade_json),
        patch("aiopvapi.rooms.Rooms.get_resources", return_value=room_json),
        patch("aiopvapi.scenes.Scenes.get_resources", return_value=scene_json),
        patch(
            "aiopvapi.scene_members.SceneMembers.get_resources",
            return_value=scenemember_json,
        ),
        patch(
            "aiopvapi.automations.Automations.get_resources",
            return_value=automation_json,
        ),
        patch("aiopvapi.resources.automation.Automation.fetch_associated_scene_data"),
    ):
        yield


@pytest.fixture
def device_json(api_version: int) -> str:
    """Return the request_raw_data fixture for a specific device."""
    if api_version == 1:
        return load_json_value_fixture("gen1/userdata.json", DOMAIN)
    if api_version == 2:
        return load_json_value_fixture("gen2/userdata.json", DOMAIN)
    if api_version == 3:
        return load_json_value_fixture("gen3/gateway/primary.json", DOMAIN)
    raise ValueError(f"Unsupported api_version: {api_version}")


@pytest.fixture
def home_json(api_version: int) -> str:
    """Return the request_home_data fixture for a specific device."""
    if api_version == 1:
        return load_json_value_fixture("gen1/userdata.json", DOMAIN)
    if api_version == 2:
        return load_json_value_fixture("gen2/userdata.json", DOMAIN)
    if api_version == 3:
        return load_json_value_fixture("gen3/home/home.json", DOMAIN)
    raise ValueError(f"Unsupported api_version: {api_version}")


@pytest.fixture
def firmware_json(api_version: int) -> str:
    """Return the request_raw_firmware fixture for a specific device."""
    if api_version == 1:
        return load_json_value_fixture("gen1/fwversion.json", DOMAIN)
    if api_version == 2:
        return load_json_value_fixture("gen2/fwversion.json", DOMAIN)
    if api_version == 3:
        return load_json_value_fixture("gen3/gateway/info.json", DOMAIN)
    raise ValueError(f"Unsupported api_version: {api_version}")


@pytest.fixture
def room_json(api_version: int) -> str:
    """Return the get_resources fixture for a specific device."""
    if api_version == 1:
        return load_json_value_fixture("gen1/rooms.json", DOMAIN)
    if api_version == 2:
        return load_json_value_fixture("gen2/rooms.json", DOMAIN)
    if api_version == 3:
        return load_json_value_fixture("gen3/home/rooms.json", DOMAIN)
    raise ValueError(f"Unsupported api_version: {api_version}")


@pytest.fixture
def scene_json(api_version: int) -> str:
    """Return the get_resources fixture for a specific device."""
    if api_version == 1:
        return load_json_value_fixture("gen1/scenes.json", DOMAIN)
    if api_version == 2:
        return load_json_value_fixture("gen2/scenes.json", DOMAIN)
    if api_version == 3:
        return load_json_value_fixture("gen3/home/scenes.json", DOMAIN)
    raise ValueError(f"Unsupported api_version: {api_version}")


@pytest.fixture
def scenemember_json(api_version: int) -> str:
    """Return the get_resources fixture for a specific device."""
    if api_version == 1:
        return load_json_value_fixture("gen1/scenemembers.json", DOMAIN)
    if api_version == 2:
        return load_json_value_fixture("gen2/scenemembers.json", DOMAIN)
    if api_version == 3:
        return "{}"  # gen3 does not have (or need) a scenemembers endpoint
    raise ValueError(f"Unsupported api_version: {api_version}")


@pytest.fixture
def shade_json(api_version: int) -> str:
    """Return the get_resources fixture for a specific device."""
    if api_version == 1:
        return load_json_value_fixture("gen1/shades.json", DOMAIN)
    if api_version == 2:
        return load_json_value_fixture("gen2/shades.json", DOMAIN)
    if api_version == 3:
        return load_json_value_fixture("gen3/home/shades.json", DOMAIN)
    raise ValueError(f"Unsupported api_version: {api_version}")


@pytest.fixture
def automation_json(api_version: int) -> str:
    """Return the automation resources fixture for a specific device."""
    if api_version == 1:
        return load_json_value_fixture("gen1/scheduledevents.json", DOMAIN)
    if api_version == 2:
        return load_json_value_fixture("gen2/scheduledevents.json", DOMAIN)
    if api_version == 3:
        return load_json_value_fixture("gen3/home/automations.json", DOMAIN)
    raise ValueError(f"Unsupported api_version: {api_version}")
