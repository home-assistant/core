"""Test the Shark IQ vacuum entity."""
from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime, timedelta
import enum
from typing import Any
from unittest.mock import patch

import pytest
from sharkiq import AylaApi, SharkIqAuthError, SharkIqNotAuthedError, SharkIqVacuum

from homeassistant import exceptions
from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.components.sharkiq import DOMAIN
from homeassistant.components.sharkiq.vacuum import (
    ATTR_ERROR_CODE,
    ATTR_ERROR_MSG,
    ATTR_LOW_LIGHT,
    ATTR_RECHARGE_RESUME,
    ATTR_ROOMS,
    FAN_SPEEDS_MAP,
    SERVICE_CLEAN_ROOM,
)
from homeassistant.components.vacuum import (
    ATTR_BATTERY_LEVEL,
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    STATE_CLEANING,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    VacuumEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .const import (
    CONFIG,
    ENTRY_ID,
    SHARK_DEVICE_DICT,
    SHARK_METADATA_DICT,
    SHARK_PROPERTIES_DICT,
    TEST_USERNAME,
)

from tests.common import MockConfigEntry

VAC_ENTITY_ID = f"vacuum.{SHARK_DEVICE_DICT['product_name'].lower()}"
ROOM_LIST = ["Kitchen", "Living Room"]
EXPECTED_FEATURES = (
    VacuumEntityFeature.BATTERY
    | VacuumEntityFeature.FAN_SPEED
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.START
    | VacuumEntityFeature.STATE
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.LOCATE
)


class MockAyla(AylaApi):
    """Mocked AylaApi that doesn't do anything."""

    desired_expiry = False

    async def async_sign_in(self):
        """Instead of signing in, just return."""

    async def async_refresh_auth(self):
        """Instead of refreshing auth, just return."""

    async def async_sign_out(self):
        """Instead of signing out, just return."""

    async def async_list_devices(self) -> list[dict]:
        """Return the device list."""
        return [SHARK_DEVICE_DICT]

    async def async_get_devices(self, update: bool = True) -> list[SharkIqVacuum]:
        """Get the list of devices."""
        shark = MockShark(self, SHARK_DEVICE_DICT)
        shark.properties_full = deepcopy(SHARK_PROPERTIES_DICT)
        shark._update_metadata(SHARK_METADATA_DICT)
        return [shark]

    async def async_request(self, http_method: str, url: str, **kwargs):
        """Don't make an HTTP request."""

    @property
    def token_expiring_soon(self) -> bool:
        """Toggling Property for Token Expiration Flag."""
        # Alternate expiry flag for each test
        self.desired_expiry = not self.desired_expiry
        return self.desired_expiry

    @property
    def auth_expiration(self) -> datetime:
        """Sample expiration timestamp that is always 1200 seconds behind now()."""
        return datetime.now() - timedelta(seconds=1200)


class MockShark(SharkIqVacuum):
    """Mocked SharkIqVacuum that won't hit the API."""

    async def async_update(self, property_list: Iterable[str] | None = None):
        """Don't do anything."""

    def set_property_value(self, property_name, value):
        """Set a property locally without hitting the API."""
        if isinstance(property_name, enum.Enum):
            property_name = property_name.value
        if isinstance(value, enum.Enum):
            value = value.value
        self.properties_full[property_name]["value"] = value

    async def async_set_property_value(self, property_name, value):
        """Set a property locally without hitting the API."""
        self.set_property_value(property_name, value)

    def get_room_list(self):
        """Return the list of available rooms without hitting the API."""
        return ROOM_LIST


@pytest.fixture(autouse=True)
@patch("sharkiq.ayla_api.AylaApi", MockAyla)
async def setup_integration(hass):
    """Build the mock integration."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=TEST_USERNAME, data=CONFIG, entry_id=ENTRY_ID
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_simple_properties(hass: HomeAssistant) -> None:
    """Test that simple properties work as intended."""
    state = hass.states.get(VAC_ENTITY_ID)
    registry = er.async_get(hass)
    entity = registry.async_get(VAC_ENTITY_ID)

    assert entity
    assert state
    assert state.state == STATE_CLEANING
    assert entity.unique_id == "AC000Wxxxxxxxxx"


@pytest.mark.parametrize(
    ("attribute", "target_value"),
    [
        (ATTR_SUPPORTED_FEATURES, EXPECTED_FEATURES),
        (ATTR_BATTERY_LEVEL, 50),
        (ATTR_FAN_SPEED, "Eco"),
        (ATTR_FAN_SPEED_LIST, list(FAN_SPEEDS_MAP)),
        (ATTR_ERROR_CODE, 7),
        (ATTR_ERROR_MSG, "Cliff sensor is blocked"),
        (ATTR_LOW_LIGHT, False),
        (ATTR_RECHARGE_RESUME, True),
        (ATTR_ROOMS, ROOM_LIST),
    ],
)
async def test_initial_attributes(
    hass: HomeAssistant, attribute: str, target_value: Any
) -> None:
    """Test initial config attributes."""
    state = hass.states.get(VAC_ENTITY_ID)
    assert state.attributes.get(attribute) == target_value


@pytest.mark.parametrize(
    ("service", "target_state"),
    [
        (SERVICE_STOP, STATE_IDLE),
        (SERVICE_PAUSE, STATE_PAUSED),
        (SERVICE_RETURN_TO_BASE, STATE_RETURNING),
        (SERVICE_START, STATE_CLEANING),
    ],
)
async def test_cleaning_states(
    hass: HomeAssistant, service: str, target_state: str
) -> None:
    """Test cleaning states."""
    service_data = {ATTR_ENTITY_ID: VAC_ENTITY_ID}
    await hass.services.async_call("vacuum", service, service_data, blocking=True)
    state = hass.states.get(VAC_ENTITY_ID)
    assert state.state == target_state


@pytest.mark.parametrize("fan_speed", list(FAN_SPEEDS_MAP))
async def test_fan_speed(hass: HomeAssistant, fan_speed: str) -> None:
    """Test setting fan speeds."""
    service_data = {ATTR_ENTITY_ID: VAC_ENTITY_ID, ATTR_FAN_SPEED: fan_speed}
    await hass.services.async_call(
        "vacuum", SERVICE_SET_FAN_SPEED, service_data, blocking=True
    )
    state = hass.states.get(VAC_ENTITY_ID)
    assert state.attributes.get(ATTR_FAN_SPEED) == fan_speed


@pytest.mark.parametrize(
    ("device_property", "target_value"),
    [
        ("manufacturer", "Shark"),
        ("model", "RV1001AE"),
        ("name", "Sharknado"),
        ("sw_version", "Dummy Firmware 1.0"),
    ],
)
async def test_device_properties(
    hass: HomeAssistant, device_property: str, target_value: str
) -> None:
    """Test device properties."""
    registry = dr.async_get(hass)
    device = registry.async_get_device(identifiers={(DOMAIN, "AC000Wxxxxxxxxx")})
    assert getattr(device, device_property) == target_value


@pytest.mark.parametrize(
    ("room_list", "exception"),
    [
        (["KITCHEN"], exceptions.HomeAssistantError),
        (["Kitchen"], None),
        (["Office"], exceptions.HomeAssistantError),
        ([], exceptions.HomeAssistantError),
    ],
)
async def test_clean_room_error(
    hass: HomeAssistant, room_list: list, exception: Exception
) -> None:
    """Test clean_room errors."""
    if exception is None:
        data = {ATTR_ENTITY_ID: VAC_ENTITY_ID, ATTR_ROOMS: room_list}
        with patch.object(SharkIqVacuum, "async_clean_rooms") as mock_clean_room:
            await hass.services.async_call(
                DOMAIN, SERVICE_CLEAN_ROOM, data, blocking=True
            )
            mock_clean_room.assert_called_once()
    else:
        with pytest.raises(exception):
            if room_list:
                data = {ATTR_ENTITY_ID: VAC_ENTITY_ID, ATTR_ROOMS: room_list}
                await hass.services.async_call(
                    DOMAIN, SERVICE_CLEAN_ROOM, data, blocking=True
                )
            elif not room_list:
                data = {ATTR_ENTITY_ID: VAC_ENTITY_ID, ATTR_ROOMS: room_list}
                await hass.services.async_call(
                    DOMAIN, SERVICE_CLEAN_ROOM, data, blocking=True
                )


async def test_locate(hass: HomeAssistant) -> None:
    """Test that the locate command works."""
    with patch.object(SharkIqVacuum, "async_find_device") as mock_locate:
        data = {ATTR_ENTITY_ID: VAC_ENTITY_ID}
        await hass.services.async_call("vacuum", SERVICE_LOCATE, data, blocking=True)
        mock_locate.assert_called_once()


@pytest.mark.parametrize(
    ("room_list"),
    [(ROOM_LIST), (["Kitchen"])],
)
async def test_clean_room(hass: HomeAssistant, room_list: list) -> None:
    """Test that the clean_room command works."""
    with patch.object(SharkIqVacuum, "async_clean_rooms") as mock_clean_room:
        data = {ATTR_ENTITY_ID: VAC_ENTITY_ID, ATTR_ROOMS: room_list}
        await hass.services.async_call(DOMAIN, SERVICE_CLEAN_ROOM, data, blocking=True)
        mock_clean_room.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "success"),
    [
        (None, True),
        (SharkIqAuthError, False),
        (SharkIqNotAuthedError, False),
        (RuntimeError, False),
    ],
)
@patch("sharkiq.ayla_api.AylaApi", MockAyla)
async def test_coordinator_updates(
    hass: HomeAssistant, side_effect: Exception | None, success: bool
) -> None:
    """Test the update coordinator update functions."""
    coordinator = hass.data[DOMAIN][ENTRY_ID]

    await async_setup_component(hass, "homeassistant", {})

    with patch.object(
        MockShark, "async_update", side_effect=side_effect
    ) as mock_update:
        data = {ATTR_ENTITY_ID: [VAC_ENTITY_ID]}
        await hass.services.async_call(
            "homeassistant", SERVICE_UPDATE_ENTITY, data, blocking=True
        )
        assert coordinator.last_update_success == success
        mock_update.assert_called_once()

    state = hass.states.get(VAC_ENTITY_ID)
    assert (state.state == STATE_UNAVAILABLE) != success
