"""Common fixtures for the Control4 tests."""

from collections.abc import AsyncGenerator, Generator
import copy
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

from homeassistant.components.control4.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform

from . import mock_director_variables

MOCK_HOST = "192.168.1.100"
MOCK_USERNAME = "test-username"
MOCK_PASSWORD = "test-password"
MOCK_CONTROLLER_UNIQUE_ID = "control4_test_123"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Controller",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
            "controller_unique_id": MOCK_CONTROLLER_UNIQUE_ID,
        },
        unique_id="00:aa:00:aa:00:aa",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock control4 setup entry."""
    with patch(
        "homeassistant.components.control4.async_setup_entry", return_value=None
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_c4_account() -> Generator[MagicMock]:
    """Mock a Control4 Account client."""
    with (
        patch(
            "homeassistant.components.control4.C4Account", autospec=True
        ) as mock_account_class,
        patch(
            "homeassistant.components.control4.config_flow.C4Account",
            new=mock_account_class,
        ),
    ):
        mock_account = mock_account_class.return_value
        mock_account.get_account_bearer_token = AsyncMock()
        mock_account.get_account_controllers = AsyncMock(
            return_value={
                "controllerCommonName": "control4_model_00AA00AA00AA",
                "href": "https://apis.control4.com/account/v3/rest/accounts/000000",
                "name": "Name",
            }
        )
        mock_account.get_director_bearer_token = AsyncMock(
            return_value={"token": "test", "validSeconds": 86400}
        )
        mock_account.get_controller_os_version = AsyncMock(return_value="3.2.0")
        yield mock_account


def _director_mock(
    all_items: list[dict[str, Any]], ui_config: dict[str, Any]
) -> Generator[MagicMock]:
    """Patch C4Director to serve the given item and ui-configuration data."""
    with (
        patch(
            "homeassistant.components.control4.C4Director", autospec=True
        ) as mock_director_class,
        patch(
            "homeassistant.components.control4.config_flow.C4Director",
            new=mock_director_class,
        ),
    ):
        mock_director = mock_director_class.return_value
        mock_director.get_all_item_info = AsyncMock(return_value=all_items)
        mock_director.get_ui_configuration = AsyncMock(return_value=ui_config)
        mock_director.get_item_variables = AsyncMock(return_value=[])
        yield mock_director


@pytest.fixture
def mock_c4_director() -> Generator[MagicMock]:
    """Mock a Control4 Director client."""
    all_items = cast(
        "list[dict[str, Any]]",
        copy.deepcopy(load_json_array_fixture("director_all_items.json", DOMAIN)),
    )
    ui_config = cast(
        "dict[str, Any]",
        copy.deepcopy(load_json_object_fixture("ui_configuration.json", DOMAIN)),
    )
    yield from _director_mock(all_items, ui_config)


@pytest.fixture
def mock_c4_director_audio_room(mock_c4_director: MagicMock) -> MagicMock:
    """Mock a Director whose only experience for room 1 is a listen one."""
    ui_config = mock_c4_director.get_ui_configuration.return_value
    ui_config["experiences"][0]["type"] = "listen"
    return mock_c4_director


@pytest.fixture
def mock_c4_director_duplicate_source_names(mock_c4_director: MagicMock) -> MagicMock:
    """Mock a Director where room 1 has two video sources named alike."""
    mock_c4_director.get_all_item_info.return_value.append({"id": 101, "name": "TV"})
    ui_config = mock_c4_director.get_ui_configuration.return_value
    ui_config["experiences"][0]["sources"]["source"].append({"id": 101})
    return mock_c4_director


@pytest.fixture
def mock_c4_director_audio_first_mixed_sources(
    mock_c4_director: MagicMock,
) -> MagicMock:
    """Mock a Director whose room 1 lists an audio source before a video one."""
    mock_c4_director.get_all_item_info.return_value.append(
        {"id": 200, "name": "Speakers"}
    )
    ui_config = mock_c4_director.get_ui_configuration.return_value
    # A listen experience ahead of the watch experience, so the audio source
    # (200) is the first one discovered for the room and the video source (100)
    # the second.
    ui_config["experiences"].insert(
        0,
        {"room_id": 1, "type": "listen", "sources": {"source": [{"id": 200}]}},
    )
    return mock_c4_director


@pytest.fixture
def mock_room_variables(mock_c4_director: MagicMock) -> None:
    """Mock the room variables reported by the director."""
    mock_director_variables(
        mock_c4_director,
        {
            1: {
                "POWER_STATE": True,
                "CURRENT_VOLUME": 50,
                "IS_MUTED": False,
                "CURRENT_VIDEO_DEVICE": 100,
                "CURRENT MEDIA INFO": {},
                "PLAYING": False,
                "PAUSED": False,
                "STOPPED": False,
            }
        },
    )


@pytest.fixture
def mock_room_off_variables() -> dict[int, dict[str, Any]]:
    """Mock room variable data for a room that is switched off."""
    return {
        1: {
            "POWER_STATE": False,
            "CURRENT_VOLUME": 50,
            "IS_MUTED": False,
            "CURRENT_VIDEO_DEVICE": 0,
            "CURRENT MEDIA INFO": {},
            "PLAYING": False,
            "PAUSED": False,
            "STOPPED": False,
        }
    }


@pytest.fixture
def mock_room_off_update_variables(
    mock_c4_director: MagicMock, mock_room_off_variables: dict[int, dict[str, Any]]
) -> None:
    """Mock the variables the director reports for a room that is switched off."""
    mock_director_variables(mock_c4_director, mock_room_off_variables)


@pytest.fixture
def mock_c4_room() -> Generator[MagicMock]:
    """Mock a C4Room client."""
    with patch(
        "homeassistant.components.control4.media_player.C4Room", autospec=True
    ) as mock_class:
        mock_instance = mock_class.return_value
        for method in (
            "set_room_off",
            "set_video_and_audio_source",
            "set_audio_source",
            "set_play",
            "set_pause",
            "set_stop",
            "set_mute_on",
            "set_mute_off",
            "set_volume",
            "set_increment_volume",
            "set_decrement_volume",
        ):
            setattr(mock_instance, method, AsyncMock())
        yield mock_instance


@pytest.fixture
def mock_climate_variables() -> dict[int, dict[str, Any]]:
    """Mock climate variable data for default thermostat state."""
    return {
        123: {
            "HVAC_STATE": "Off",
            "HVAC_MODE": "Heat",
            "TEMPERATURE_F": 72.5,
            "HUMIDITY": 45,
            "COOL_SETPOINT_F": 75.0,
            "HEAT_SETPOINT_F": 68.0,
            "FAN_MODE": "Auto",
            "FAN_MODES_LIST": "Auto,On,Circulate",
            "SCALE": "FAHRENHEIT",
        }
    }


@pytest.fixture
def mock_climate_update_variables(
    mock_c4_director: MagicMock, mock_climate_variables: dict[int, dict[str, Any]]
) -> None:
    """Mock the climate variables reported by the director."""
    mock_director_variables(mock_c4_director, mock_climate_variables)


@pytest.fixture
def mock_c4_climate() -> Generator[MagicMock]:
    """Mock C4Climate class."""
    with patch(
        "homeassistant.components.control4.climate.C4Climate", autospec=True
    ) as mock_class:
        mock_instance = mock_class.return_value
        mock_instance.set_hvac_mode = AsyncMock()
        mock_instance.set_heat_setpoint_f = AsyncMock()
        mock_instance.set_cool_setpoint_f = AsyncMock()
        mock_instance.set_fan_mode = AsyncMock()
        mock_instance.set_heat_setpoint_c = AsyncMock()
        mock_instance.set_cool_setpoint_c = AsyncMock()
        yield mock_instance


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms which should be loaded during the test."""
    return [Platform.MEDIA_PLAYER]


@pytest.fixture(autouse=True)
async def mock_patch_platforms(platforms: list[Platform]) -> AsyncGenerator[None]:
    """Fixture to set up platforms for tests."""
    with patch("homeassistant.components.control4.PLATFORMS", platforms):
        yield
