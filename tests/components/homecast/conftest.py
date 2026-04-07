"""Test configuration and fixtures for the Homecast integration."""

from collections.abc import Generator
import copy
import time
from unittest.mock import AsyncMock, patch

from pyhomecast import HomecastDevice, HomecastHome, HomecastState
import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.homecast.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MOCK_STATE = HomecastState(
    devices={
        "my_home_0bf8.living_room_a1b2.ceiling_light_c3d4": HomecastDevice(
            unique_id="my_home_0bf8.living_room_a1b2.ceiling_light_c3d4",
            name="Ceiling Light",
            room_name="Living Room",
            home_key="my_home_0bf8",
            home_name="My Home",
            room_key="living_room_a1b2",
            accessory_key="ceiling_light_c3d4",
            device_type="light",
            state={"on": True, "brightness": 80, "hue": 45, "saturation": 100},
            settable=["on", "brightness", "hue", "saturation"],
        ),
        "my_home_0bf8.living_room_a1b2.smart_plug_e5f6": HomecastDevice(
            unique_id="my_home_0bf8.living_room_a1b2.smart_plug_e5f6",
            name="Smart Plug",
            room_name="Living Room",
            home_key="my_home_0bf8",
            home_name="My Home",
            room_key="living_room_a1b2",
            accessory_key="smart_plug_e5f6",
            device_type="switch",
            state={"on": False},
            settable=["on"],
        ),
        "my_home_0bf8.bedroom_7890.thermostat_abcd": HomecastDevice(
            unique_id="my_home_0bf8.bedroom_7890.thermostat_abcd",
            name="Thermostat",
            room_name="Bedroom",
            home_key="my_home_0bf8",
            home_name="My Home",
            room_key="bedroom_7890",
            accessory_key="thermostat_abcd",
            device_type="climate",
            state={
                "current_temp": 20.5,
                "heat_target": 21.0,
                "cool_target": 25.0,
                "hvac_mode": "auto",
                "hvac_state": "heating",
                "active": True,
            },
            settable=["heat_target", "cool_target", "hvac_mode", "active"],
        ),
        "my_home_0bf8.hallway_1234.front_door_5678": HomecastDevice(
            unique_id="my_home_0bf8.hallway_1234.front_door_5678",
            name="Front Door",
            room_name="Hallway",
            home_key="my_home_0bf8",
            home_name="My Home",
            room_key="hallway_1234",
            accessory_key="front_door_5678",
            device_type="lock",
            state={"locked": True},
            settable=["lock_target"],
        ),
        "my_home_0bf8.hallway_1234.motion_sensor_9abc": HomecastDevice(
            unique_id="my_home_0bf8.hallway_1234.motion_sensor_9abc",
            name="Motion Sensor",
            room_name="Hallway",
            home_key="my_home_0bf8",
            home_name="My Home",
            room_key="hallway_1234",
            accessory_key="motion_sensor_9abc",
            device_type="motion",
            state={"motion": False, "battery": 85, "low_battery": False},
            settable=[],
        ),
    },
    homes={
        "my_home_0bf8": HomecastHome(
            key="my_home_0bf8",
            name="My Home",
            home_id="EEBCDDC0-F66D-5BD2-8D0E-C28CEC3FB454",
        ),
    },
)


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the OAuth token expiration time."""
    return time.time() + 3600


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to set up application credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("CLIENT_ID", "CLIENT_SECRET"),
        DOMAIN,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.homecast.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_homecast() -> Generator[AsyncMock]:
    """Mock HomecastClient and HomecastWebSocket."""
    with (
        patch(
            "homeassistant.components.homecast.HomecastClient",
            autospec=True,
        ) as mock_client_class,
        patch(
            "homeassistant.components.homecast.config_flow.HomecastClient",
            new=mock_client_class,
        ),
        patch(
            "homeassistant.components.homecast.HomecastWebSocket",
            autospec=True,
        ) as mock_ws_class,
    ):
        client = mock_client_class.return_value
        client.get_state = AsyncMock(side_effect=lambda **kw: copy.deepcopy(MOCK_STATE))
        client.set_state = AsyncMock(return_value={"ok": True})
        client.run_scene = AsyncMock(return_value={"ok": True})
        client.register_client = AsyncMock(
            return_value={"client_id": "test-id", "client_secret": "test-secret"}
        )
        client.authenticate = lambda token: None  # sync method, not async
        client._token = "mock-access-token"

        ws = mock_ws_class.return_value
        ws.connect = AsyncMock()
        ws.disconnect = AsyncMock()
        ws.subscribe = AsyncMock()
        ws.set_callback = lambda cb: None
        ws.set_token = lambda token: None
        ws.connected = True

        yield client


@pytest.fixture
def mock_config_entry(expires_at: int) -> MockConfigEntry:
    """Create a mock Homecast config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Homecast",
        unique_id="EEBCDDC0-F66D-5BD2-8D0E-C28CEC3FB454",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "expires_at": expires_at,
                "scope": "mcp:read mcp:write",
            },
        },
    )
