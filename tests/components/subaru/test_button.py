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

from .api_responses import (
    TEST_VIN_2_EV,
    TEST_VIN_3_G3,
    VEHICLE_DATA,
    VEHICLE_STATUS_EV,
    VEHICLE_STATUS_G3,
)
from .conftest import (
    MOCK_API,
    MOCK_API_FETCH,
    MOCK_API_GET_DATA,
    setup_subaru_config_entry,
)

from tests.common import MockConfigEntry

MOCK_API_REMOTE_START = f"{MOCK_API}remote_start"
MOCK_API_REMOTE_STOP = f"{MOCK_API}remote_stop"

VEHICLE_BUTTONS = {
    TEST_VIN_2_EV: {
        "remote_start": "button.test_vehicle_2_remote_start",
        "remote_stop": "button.test_vehicle_2_remote_stop",
    },
    TEST_VIN_3_G3: {
        "remote_start": "button.test_vehicle_3_remote_start",
        "remote_stop": "button.test_vehicle_3_remote_stop",
    },
}


@pytest.mark.parametrize("vin", [TEST_VIN_2_EV, TEST_VIN_3_G3])
async def test_device_exists(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
    vin: str,
) -> None:
    """Test subaru remote button entities exist."""
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[vin],
        vehicle_data=VEHICLE_DATA[vin],
    )
    entry = entity_registry.async_get(VEHICLE_BUTTONS[vin]["remote_start"])
    assert entry
    entry = entity_registry.async_get(VEHICLE_BUTTONS[vin]["remote_stop"])
    assert entry


@pytest.mark.parametrize(
    ("vin", "vehicle_status"),
    [
        (TEST_VIN_2_EV, VEHICLE_STATUS_EV),
        (TEST_VIN_3_G3, VEHICLE_STATUS_G3),
    ],
)
async def test_remote_start(
    hass: HomeAssistant,
    subaru_config_entry: MockConfigEntry,
    vin: str,
    vehicle_status: dict,
) -> None:
    """Test subaru remote start button."""
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[vin],
        vehicle_data=VEHICLE_DATA[vin],
    )
    with (
        patch(MOCK_API_REMOTE_START) as mock_remote_start,
        patch(MOCK_API_FETCH),
        patch(MOCK_API_GET_DATA, return_value=vehicle_status),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: VEHICLE_BUTTONS[vin]["remote_start"]},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_remote_start.assert_called_once()


@pytest.mark.parametrize(
    ("vin", "vehicle_status"),
    [
        (TEST_VIN_2_EV, VEHICLE_STATUS_EV),
        (TEST_VIN_3_G3, VEHICLE_STATUS_G3),
    ],
)
async def test_remote_stop(
    hass: HomeAssistant,
    subaru_config_entry: MockConfigEntry,
    vin: str,
    vehicle_status: dict,
) -> None:
    """Test subaru remote stop button."""
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[vin],
        vehicle_data=VEHICLE_DATA[vin],
    )
    with (
        patch(MOCK_API_REMOTE_STOP) as mock_remote_stop,
        patch(MOCK_API_FETCH),
        patch(MOCK_API_GET_DATA, return_value=vehicle_status),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: VEHICLE_BUTTONS[vin]["remote_stop"]},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_remote_stop.assert_called_once()


@pytest.mark.parametrize(
    ("vin", "vehicle_status"),
    [
        (TEST_VIN_2_EV, VEHICLE_STATUS_EV),
        (TEST_VIN_3_G3, VEHICLE_STATUS_G3),
    ],
)
async def test_remote_start_fails(
    hass: HomeAssistant,
    subaru_config_entry: MockConfigEntry,
    vin: str,
    vehicle_status: dict,
) -> None:
    """Test subaru remote start button failure."""
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[vin],
        vehicle_data=VEHICLE_DATA[vin],
    )
    with (
        patch(MOCK_API_REMOTE_START, return_value=False),
        patch(MOCK_API_FETCH),
        patch(MOCK_API_GET_DATA, return_value=vehicle_status),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: VEHICLE_BUTTONS[vin]["remote_start"]},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("vin", "vehicle_status"),
    [
        (TEST_VIN_2_EV, VEHICLE_STATUS_EV),
        (TEST_VIN_3_G3, VEHICLE_STATUS_G3),
    ],
)
async def test_remote_start_exception(
    hass: HomeAssistant,
    subaru_config_entry: MockConfigEntry,
    vin: str,
    vehicle_status: dict,
) -> None:
    """Test subaru remote start button with SubaruException."""
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[vin],
        vehicle_data=VEHICLE_DATA[vin],
    )
    with (
        patch(
            MOCK_API_REMOTE_START,
            side_effect=SubaruException("Remote service failed"),
        ),
        patch(MOCK_API_FETCH),
        patch(MOCK_API_GET_DATA, return_value=vehicle_status),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: VEHICLE_BUTTONS[vin]["remote_start"]},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("vin", "vehicle_status"),
    [
        (TEST_VIN_2_EV, VEHICLE_STATUS_EV),
        (TEST_VIN_3_G3, VEHICLE_STATUS_G3),
    ],
)
async def test_remote_stop_fails(
    hass: HomeAssistant,
    subaru_config_entry: MockConfigEntry,
    vin: str,
    vehicle_status: dict,
) -> None:
    """Test subaru remote stop button failure."""
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[vin],
        vehicle_data=VEHICLE_DATA[vin],
    )
    with (
        patch(MOCK_API_REMOTE_STOP, return_value=False),
        patch(MOCK_API_FETCH),
        patch(MOCK_API_GET_DATA, return_value=vehicle_status),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: VEHICLE_BUTTONS[vin]["remote_stop"]},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("vin", "vehicle_status"),
    [
        (TEST_VIN_2_EV, VEHICLE_STATUS_EV),
        (TEST_VIN_3_G3, VEHICLE_STATUS_G3),
    ],
)
async def test_remote_stop_exception(
    hass: HomeAssistant,
    subaru_config_entry: MockConfigEntry,
    vin: str,
    vehicle_status: dict,
) -> None:
    """Test subaru remote stop button with SubaruException."""
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[vin],
        vehicle_data=VEHICLE_DATA[vin],
    )
    with (
        patch(
            MOCK_API_REMOTE_STOP,
            side_effect=SubaruException("Remote service failed"),
        ),
        patch(MOCK_API_FETCH),
        patch(MOCK_API_GET_DATA, return_value=vehicle_status),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: VEHICLE_BUTTONS[vin]["remote_stop"]},
            blocking=True,
        )


async def test_no_buttons_without_remote_start(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
) -> None:
    """Test no buttons created for vehicle without remote start or EV."""
    vehicle_data = {
        **VEHICLE_DATA[TEST_VIN_3_G3],
        VEHICLE_HAS_REMOTE_START: False,
        VEHICLE_HAS_EV: False,
    }
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[TEST_VIN_3_G3],
        vehicle_data=vehicle_data,
    )
    entry = entity_registry.async_get(VEHICLE_BUTTONS[TEST_VIN_3_G3]["remote_start"])
    assert entry is None
    entry = entity_registry.async_get(VEHICLE_BUTTONS[TEST_VIN_3_G3]["remote_stop"])
    assert entry is None
