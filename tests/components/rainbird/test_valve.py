"""Tests for rainbird valve platform."""

from http import HTTPStatus

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import (
    ACK_ECHO,
    EMPTY_STATIONS_RESPONSE,
    RAIN_DELAY_OFF,
    RAIN_SENSOR_OFF,
    ZONE_3_ON_RESPONSE,
    ZONE_5_ON_RESPONSE,
    ZONE_OFF_RESPONSE,
    mock_response,
    mock_response_error,
)
from homeassistant.components.rainbird.const import (
    ATTR_DURATION,
    CONF_ZONE_TYPE,
    DEFAULT_TRIGGER_TIME_MINUTES,
    DOMAIN,
    ZONE_TYPE_VALVE,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.VALVE]


@pytest.fixture
async def config_entry(
    config_entry_data: dict,
    config_entry_unique_id: str | None,
) -> MockConfigEntry:
    """Fixture for MockConfigEntry with valve zone type."""
    return MockConfigEntry(
        unique_id=config_entry_unique_id,
        domain=DOMAIN,
        data=config_entry_data,
        options={
            ATTR_DURATION: DEFAULT_TRIGGER_TIME_MINUTES,
            CONF_ZONE_TYPE: ZONE_TYPE_VALVE,
        },
    )


@pytest.fixture(autouse=True)
async def setup_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> list[Platform]:
    """Fixture to setup the config entry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "stations_response",
    [EMPTY_STATIONS_RESPONSE],
)
async def test_no_zones(
    hass: HomeAssistant,
) -> None:
    """Test case where listing stations returns no stations."""
    assert hass.states.get("valve.rain_bird_sprinkler_1") is None


@pytest.mark.parametrize(
    "zone_state_response",
    [ZONE_5_ON_RESPONSE],
)
async def test_zones(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test valve platform with fake data that creates 7 zones with one open."""
    zone = hass.states.get("valve.rain_bird_sprinkler_1")
    assert zone is not None
    assert zone.state == "closed"
    assert zone.attributes.get("zone") == 1

    zone = hass.states.get("valve.rain_bird_sprinkler_5")
    assert zone is not None
    assert zone.state == "open"

    assert not hass.states.get("valve.rain_bird_sprinkler_8")

    entity_entry = entity_registry.async_get("valve.rain_bird_sprinkler_3")
    assert entity_entry.unique_id == "4c:a1:61:00:11:22-3"


async def test_valve_open(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
) -> None:
    """Test opening an irrigation valve."""
    zone = hass.states.get("valve.rain_bird_sprinkler_3")
    assert zone is not None
    assert zone.state == "closed"

    aioclient_mock.mock_calls.clear()
    responses.extend(
        [
            mock_response(ACK_ECHO),
            mock_response(ZONE_3_ON_RESPONSE),
            mock_response(RAIN_SENSOR_OFF),
            mock_response(RAIN_DELAY_OFF),
        ]
    )
    await hass.services.async_call(
        "valve",
        "open_valve",
        {ATTR_ENTITY_ID: "valve.rain_bird_sprinkler_3"},
        blocking=True,
    )
    await hass.async_block_till_done()

    zone = hass.states.get("valve.rain_bird_sprinkler_3")
    assert zone is not None
    assert zone.state == "open"


@pytest.mark.parametrize(
    ("zone_state_response", "start_state"),
    [
        pytest.param(ZONE_3_ON_RESPONSE, "open", id="zone_open"),
        pytest.param(ZONE_OFF_RESPONSE, "closed", id="zone_closed"),
    ],
)
async def test_valve_close(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
    start_state: str,
) -> None:
    """Test closing an irrigation valve."""
    zone = hass.states.get("valve.rain_bird_sprinkler_3")
    assert zone is not None
    assert zone.state == start_state

    aioclient_mock.mock_calls.clear()
    responses.extend(
        [
            mock_response(ACK_ECHO),
            mock_response(ZONE_OFF_RESPONSE),
            mock_response(RAIN_SENSOR_OFF),
            mock_response(RAIN_DELAY_OFF),
        ]
    )
    await hass.services.async_call(
        "valve",
        "close_valve",
        {ATTR_ENTITY_ID: "valve.rain_bird_sprinkler_3"},
        blocking=True,
    )
    await hass.async_block_till_done()

    zone = hass.states.get("valve.rain_bird_sprinkler_3")
    assert zone is not None
    assert zone.state == "closed"


@pytest.mark.parametrize(
    ("status", "expected_msg"),
    [
        (HTTPStatus.SERVICE_UNAVAILABLE, "Rain Bird device is busy"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, "Rain Bird device failure"),
    ],
)
async def test_valve_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
    status: HTTPStatus,
    expected_msg: str,
) -> None:
    """Test an error talking to the device."""
    aioclient_mock.mock_calls.clear()
    responses.append(mock_response_error(status=status))

    with pytest.raises(HomeAssistantError, match=expected_msg):
        await hass.services.async_call(
            "valve",
            "open_valve",
            {ATTR_ENTITY_ID: "valve.rain_bird_sprinkler_3"},
            blocking=True,
        )

    responses.append(mock_response_error(status=status))

    with pytest.raises(HomeAssistantError, match=expected_msg):
        await hass.services.async_call(
            "valve",
            "close_valve",
            {ATTR_ENTITY_ID: "valve.rain_bird_sprinkler_3"},
            blocking=True,
        )


async def test_irrigation_service(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
) -> None:
    """Test calling the start_irrigation service in valve mode."""
    zone = hass.states.get("valve.rain_bird_sprinkler_3")
    assert zone is not None
    assert zone.state == "closed"

    aioclient_mock.mock_calls.clear()
    responses.extend(
        [
            mock_response(ACK_ECHO),
            mock_response(ZONE_3_ON_RESPONSE),
            mock_response(RAIN_SENSOR_OFF),
            mock_response(RAIN_DELAY_OFF),
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        "start_irrigation",
        {ATTR_ENTITY_ID: "valve.rain_bird_sprinkler_3", "duration": 30},
        blocking=True,
    )

    zone = hass.states.get("valve.rain_bird_sprinkler_3")
    assert zone is not None
    assert zone.state == "open"
