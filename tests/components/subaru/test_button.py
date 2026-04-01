"""Test Subaru buttons."""

from unittest.mock import patch

import pytest
from subarulink import SubaruException

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.subaru.const import (
    VEHICLE_HAS_EV,
    VEHICLE_HAS_REMOTE_START,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .api_responses import TEST_VIN_1_G1, VEHICLE_DATA, VEHICLE_STATUS_EV
from .conftest import (
    MOCK_API,
    MOCK_API_FETCH,
    MOCK_API_GET_DATA,
    setup_subaru_config_entry,
)

from tests.common import MockConfigEntry

MOCK_API_REMOTE_START = f"{MOCK_API}remote_start"
MOCK_API_REMOTE_STOP = f"{MOCK_API}remote_stop"
REMOTE_START_BUTTON = "button.test_vehicle_2_remote_start"
REMOTE_STOP_BUTTON = "button.test_vehicle_2_remote_stop"
G1_REMOTE_START_BUTTON = "button.test_vehicle_1_remote_start"


async def test_device_exists(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, ev_entry: MockConfigEntry
) -> None:
    """Test subaru remote start button entity exists."""
    entry = entity_registry.async_get(REMOTE_START_BUTTON)
    assert entry
    entry = entity_registry.async_get(REMOTE_STOP_BUTTON)
    assert entry


async def test_device_exists_non_ev(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
) -> None:
    """Test subaru remote start button exists for non-EV vehicle with remote start."""
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[TEST_VIN_1_G1],
        vehicle_data=VEHICLE_DATA[TEST_VIN_1_G1],
    )
    entry = entity_registry.async_get(G1_REMOTE_START_BUTTON)
    assert entry


async def test_remote_start(hass: HomeAssistant, ev_entry: MockConfigEntry) -> None:
    """Test subaru remote start button."""
    with (
        patch(MOCK_API_REMOTE_START) as mock_remote_start,
        patch(MOCK_API_FETCH),
        patch(MOCK_API_GET_DATA, return_value=VEHICLE_STATUS_EV),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: REMOTE_START_BUTTON},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_remote_start.assert_called_once()


async def test_remote_stop(hass: HomeAssistant, ev_entry: MockConfigEntry) -> None:
    """Test subaru remote stop button."""
    with (
        patch(MOCK_API_REMOTE_STOP) as mock_remote_stop,
        patch(MOCK_API_FETCH),
        patch(MOCK_API_GET_DATA, return_value=VEHICLE_STATUS_EV),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: REMOTE_STOP_BUTTON},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_remote_stop.assert_called_once()


async def test_remote_start_fails(
    hass: HomeAssistant, ev_entry: MockConfigEntry
) -> None:
    """Test subaru remote start button failure."""
    with (
        patch(MOCK_API_REMOTE_START, return_value=False),
        patch(MOCK_API_FETCH),
        patch(MOCK_API_GET_DATA, return_value=VEHICLE_STATUS_EV),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: REMOTE_START_BUTTON},
            blocking=True,
        )


async def test_remote_start_exception(
    hass: HomeAssistant, ev_entry: MockConfigEntry
) -> None:
    """Test subaru remote start button with SubaruException."""
    with (
        patch(
            MOCK_API_REMOTE_START,
            side_effect=SubaruException("Remote service failed"),
        ),
        patch(MOCK_API_FETCH),
        patch(MOCK_API_GET_DATA, return_value=VEHICLE_STATUS_EV),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: REMOTE_START_BUTTON},
            blocking=True,
        )


async def test_no_buttons_without_remote_start(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
) -> None:
    """Test no buttons created for vehicle without remote start or EV."""
    vehicle_data = {
        **VEHICLE_DATA[TEST_VIN_1_G1],
        VEHICLE_HAS_REMOTE_START: False,
        VEHICLE_HAS_EV: False,
    }
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[TEST_VIN_1_G1],
        vehicle_data=vehicle_data,
    )
    entry = entity_registry.async_get(G1_REMOTE_START_BUTTON)
    assert entry is None
