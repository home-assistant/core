"""Common fixtures for the Control4 tests."""

from collections.abc import AsyncGenerator, Generator
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.control4.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

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
        "homeassistant.components.control4.async_setup_entry", return_value=True
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


@pytest.fixture
def mock_c4_director() -> Generator[MagicMock]:
    """Mock a Control4 Director client."""
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
        mock_director.director_bearer_token = "test"
        all_items = json.loads(load_fixture("director_all_items.json", DOMAIN))
        mock_director.get_all_item_info = AsyncMock(return_value=all_items)
        mock_director.get_all_items_by_category = AsyncMock(return_value=all_items)
        mock_director.get_ui_configuration = AsyncMock(
            return_value=json.loads(load_fixture("ui_configuration.json", DOMAIN))
        )
        mock_director.get_item_variables = AsyncMock(return_value=[])
        mock_director.get_item_setup = AsyncMock(return_value={})
        yield mock_director


@pytest.fixture(autouse=True)
def mock_c4_websocket() -> Generator[MagicMock]:
    """Mock C4Websocket to prevent real WebSocket connections during tests.

    Tracks item callbacks in a real dict and captures the disconnect
    callback so tests can drive disconnects through the same path the
    integration uses, instead of poking entity internals directly.
    """
    item_callbacks: dict[int, list] = {}

    def _add_item_callback(item_id, callback):
        item_callbacks.setdefault(item_id, []).append(callback)

    def _remove_item_callback(item_id, callback):
        callbacks = item_callbacks.get(item_id, [])
        if callback in callbacks:
            callbacks.remove(callback)

    with patch(
        "homeassistant.components.control4.C4Websocket", autospec=True
    ) as mock_ws_class:
        mock_ws = mock_ws_class.return_value
        mock_ws.sio_connect = AsyncMock()
        mock_ws.sio_disconnect = AsyncMock()
        mock_ws.add_item_callback = MagicMock(side_effect=_add_item_callback)
        mock_ws.remove_item_callback = MagicMock(side_effect=_remove_item_callback)
        mock_ws.item_callbacks = item_callbacks
        mock_ws.disconnect_callback = None

        def _capture_callbacks(*args, **kwargs):
            mock_ws.disconnect_callback = kwargs.get(
                "disconnect_callback", args[3] if len(args) > 3 else None
            )
            return mock_ws

        mock_ws_class.side_effect = _capture_callbacks
        yield mock_ws


@pytest.fixture
def mock_update_variables() -> Generator[AsyncMock]:
    """Mock the update_variables_for_config_entry function for media_player."""

    async def _mock_update_variables(*args, **kwargs):
        return {
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
        }

    with patch(
        "homeassistant.components.control4.media_player.update_variables_for_config_entry",
        new=_mock_update_variables,
    ) as mock_update:
        yield mock_update


@pytest.fixture
def mock_climate_variables() -> dict:
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
            "HVAC_MODES_LIST": "Off,Heat,Cool,Auto",
            "SCALE": "FAHRENHEIT",
        }
    }


@pytest.fixture
def mock_climate_update_variables(
    mock_climate_variables: dict,
) -> Generator[AsyncMock]:
    """Mock director_get_entry_variables for climate platform."""

    async def _mock_get_entry_variables(hass: HomeAssistant | None, entry, item_id):
        return mock_climate_variables.get(item_id)

    with patch(
        "homeassistant.components.control4.climate.director_get_entry_variables",
        new=_mock_get_entry_variables,
    ) as mock_update:
        yield mock_update


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
