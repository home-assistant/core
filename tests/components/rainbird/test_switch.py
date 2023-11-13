"""Tests for rainbird sensor platform."""

from http import HTTPStatus

import pytest

from homeassistant.components.rainbird import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import (
    ACK_ECHO,
    EMPTY_STATIONS_RESPONSE,
    HOST,
    PASSWORD,
    RAIN_DELAY_OFF,
    RAIN_SENSOR_OFF,
    SERIAL_NUMBER,
    ZONE_3_ON_RESPONSE,
    ZONE_5_ON_RESPONSE,
    ZONE_OFF_RESPONSE,
    ComponentSetup,
    mock_response,
    mock_response_error,
)

from tests.components.switch import common as switch_common
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


@pytest.mark.parametrize(
    "stations_response",
    [EMPTY_STATIONS_RESPONSE],
)
async def test_no_zones(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test case where listing stations returns no stations."""

    assert await setup_integration()

    zone = hass.states.get("switch.rain_bird_sprinkler_1")
    assert zone is None


@pytest.mark.parametrize(
    "zone_state_response",
    [ZONE_5_ON_RESPONSE],
)
async def test_zones(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch platform with fake data that creates 7 zones with one enabled."""

    assert await setup_integration()

    zone = hass.states.get("switch.rain_bird_sprinkler_1")
    assert zone is not None
    assert zone.state == "off"
    assert zone.attributes == {
        "friendly_name": "Rain Bird Sprinkler 1",
        "zone": 1,
    }

    zone = hass.states.get("switch.rain_bird_sprinkler_2")
    assert zone is not None
    assert zone.state == "off"
    assert zone.attributes == {
        "friendly_name": "Rain Bird Sprinkler 2",
        "zone": 2,
    }

    zone = hass.states.get("switch.rain_bird_sprinkler_3")
    assert zone is not None
    assert zone.state == "off"

    zone = hass.states.get("switch.rain_bird_sprinkler_4")
    assert zone is not None
    assert zone.state == "off"

    zone = hass.states.get("switch.rain_bird_sprinkler_5")
    assert zone is not None
    assert zone.state == "on"

    zone = hass.states.get("switch.rain_bird_sprinkler_6")
    assert zone is not None
    assert zone.state == "off"

    zone = hass.states.get("switch.rain_bird_sprinkler_7")
    assert zone is not None
    assert zone.state == "off"

    assert not hass.states.get("switch.rain_bird_sprinkler_8")

    # Verify unique id for one of the switches
    entity_entry = entity_registry.async_get("switch.rain_bird_sprinkler_3")
    assert entity_entry.unique_id == "1263613994342-3"


async def test_switch_on(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
) -> None:
    """Test turning on irrigation switch."""

    assert await setup_integration()

    # Initially all zones are off. Pick zone3 as an arbitrary to assert
    # state, then update below as a switch.
    zone = hass.states.get("switch.rain_bird_sprinkler_3")
    assert zone is not None
    assert zone.state == "off"

    aioclient_mock.mock_calls.clear()
    responses.extend(
        [
            mock_response(ACK_ECHO),  # Switch on response
            # API responses when state is refreshed
            mock_response(ZONE_3_ON_RESPONSE),
            mock_response(RAIN_SENSOR_OFF),
            mock_response(RAIN_DELAY_OFF),
        ]
    )
    await switch_common.async_turn_on(hass, "switch.rain_bird_sprinkler_3")
    await hass.async_block_till_done()

    # Verify switch state is updated
    zone = hass.states.get("switch.rain_bird_sprinkler_3")
    assert zone is not None
    assert zone.state == "on"


@pytest.mark.parametrize(
    "zone_state_response",
    [ZONE_3_ON_RESPONSE],
)
async def test_switch_off(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
) -> None:
    """Test turning off irrigation switch."""

    assert await setup_integration()

    # Initially the test zone is on
    zone = hass.states.get("switch.rain_bird_sprinkler_3")
    assert zone is not None
    assert zone.state == "on"

    aioclient_mock.mock_calls.clear()
    responses.extend(
        [
            mock_response(ACK_ECHO),  # Switch off response
            mock_response(ZONE_OFF_RESPONSE),  # Updated zone state
            mock_response(RAIN_SENSOR_OFF),
            mock_response(RAIN_DELAY_OFF),
        ]
    )
    await switch_common.async_turn_off(hass, "switch.rain_bird_sprinkler_3")
    await hass.async_block_till_done()

    # Verify switch state is updated
    zone = hass.states.get("switch.rain_bird_sprinkler_3")
    assert zone is not None
    assert zone.state == "off"


async def test_irrigation_service(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
    api_responses: list[str],
) -> None:
    """Test calling the irrigation service."""

    assert await setup_integration()

    zone = hass.states.get("switch.rain_bird_sprinkler_3")
    assert zone is not None
    assert zone.state == "off"

    aioclient_mock.mock_calls.clear()
    responses.extend(
        [
            mock_response(ACK_ECHO),
            # API responses when state is refreshed
            mock_response(ZONE_3_ON_RESPONSE),
            mock_response(RAIN_SENSOR_OFF),
            mock_response(RAIN_DELAY_OFF),
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        "start_irrigation",
        {ATTR_ENTITY_ID: "switch.rain_bird_sprinkler_3", "duration": 30},
        blocking=True,
    )

    zone = hass.states.get("switch.rain_bird_sprinkler_3")
    assert zone is not None
    assert zone.state == "on"


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_data"),
    [
        (
            {},
            {
                "host": HOST,
                "password": PASSWORD,
                "trigger_time": 360,
                "serial_number": "0x1263613994342",
                "imported_names": {
                    "1": "Garden Sprinkler",
                    "2": "Back Yard",
                },
            },
        )
    ],
)
async def test_yaml_imported_config(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    responses: list[AiohttpClientMockResponse],
) -> None:
    """Test a config entry that was previously imported from yaml."""
    assert await setup_integration()

    assert hass.states.get("switch.garden_sprinkler")
    assert not hass.states.get("switch.rain_bird_sprinkler_1")
    assert hass.states.get("switch.back_yard")
    assert not hass.states.get("switch.rain_bird_sprinkler_2")
    assert hass.states.get("switch.rain_bird_sprinkler_3")


@pytest.mark.parametrize(
    ("status", "expected_msg"),
    [
        (HTTPStatus.SERVICE_UNAVAILABLE, "Rain Bird device is busy"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, "Rain Bird device failure"),
    ],
)
async def test_switch_error(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
    status: HTTPStatus,
    expected_msg: str,
) -> None:
    """Test an error talking to the device."""

    assert await setup_integration()

    aioclient_mock.mock_calls.clear()
    responses.append(mock_response_error(status=status))

    with pytest.raises(HomeAssistantError, match=expected_msg):
        await switch_common.async_turn_on(hass, "switch.rain_bird_sprinkler_3")
        await hass.async_block_till_done()

    responses.append(mock_response_error(status=status))

    with pytest.raises(HomeAssistantError, match=expected_msg):
        await switch_common.async_turn_off(hass, "switch.rain_bird_sprinkler_3")
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("config_entry_unique_id"),
    [
        (None),
    ],
)
async def test_no_unique_id(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an irrigation switch with no unique id."""

    assert await setup_integration()

    zone = hass.states.get("switch.rain_bird_sprinkler_3")
    assert zone is not None
    assert zone.attributes.get("friendly_name") == "Rain Bird Sprinkler 3"
    assert zone.state == "off"

    entity_entry = entity_registry.async_get("switch.rain_bird_sprinkler_3")
    assert entity_entry is None


@pytest.mark.parametrize(
    ("config_entry_unique_id", "entity_unique_id"),
    [
        (SERIAL_NUMBER, "1263613994342-3"),
        # Some existing config entries may have a "0" serial number but preserve
        # their unique id
        (0, "0-3"),
    ],
)
async def test_has_unique_id(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
    entity_registry: er.EntityRegistry,
    entity_unique_id: str,
) -> None:
    """Test an irrigation switch with no unique id."""

    assert await setup_integration()

    zone = hass.states.get("switch.rain_bird_sprinkler_3")
    assert zone is not None
    assert zone.attributes.get("friendly_name") == "Rain Bird Sprinkler 3"
    assert zone.state == "off"

    entity_entry = entity_registry.async_get("switch.rain_bird_sprinkler_3")
    assert entity_entry
    assert entity_entry.unique_id == entity_unique_id
