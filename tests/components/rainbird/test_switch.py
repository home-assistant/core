"""Tests for rainbird sensor platform."""


from http import HTTPStatus
import logging

import pytest

from homeassistant.components.rainbird import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from .conftest import (
    ACK_ECHO,
    AVAILABLE_STATIONS_RESPONSE,
    EMPTY_STATIONS_RESPONSE,
    HOST,
    PASSWORD,
    URL,
    ZONE_3_ON_RESPONSE,
    ZONE_5_ON_RESPONSE,
    ZONE_OFF_RESPONSE,
    ComponentSetup,
    mock_response,
)

from tests.components.switch import common as switch_common
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


async def test_no_zones(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    responses: list[AiohttpClientMockResponse],
) -> None:
    """Test case where listing stations returns no stations."""

    responses.append(mock_response(EMPTY_STATIONS_RESPONSE))
    assert await setup_integration()

    zone = hass.states.get("switch.sprinkler_1")
    assert zone is None


async def test_zones(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    responses: list[AiohttpClientMockResponse],
) -> None:
    """Test switch platform with fake data that creates 7 zones with one enabled."""

    responses.extend(
        [mock_response(AVAILABLE_STATIONS_RESPONSE), mock_response(ZONE_5_ON_RESPONSE)]
    )

    assert await setup_integration()

    zone = hass.states.get("switch.sprinkler_1")
    assert zone is not None
    assert zone.state == "off"

    zone = hass.states.get("switch.sprinkler_2")
    assert zone is not None
    assert zone.state == "off"

    zone = hass.states.get("switch.sprinkler_3")
    assert zone is not None
    assert zone.state == "off"

    zone = hass.states.get("switch.sprinkler_4")
    assert zone is not None
    assert zone.state == "off"

    zone = hass.states.get("switch.sprinkler_5")
    assert zone is not None
    assert zone.state == "on"

    zone = hass.states.get("switch.sprinkler_6")
    assert zone is not None
    assert zone.state == "off"

    zone = hass.states.get("switch.sprinkler_7")
    assert zone is not None
    assert zone.state == "off"

    assert not hass.states.get("switch.sprinkler_8")


async def test_switch_on(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
) -> None:
    """Test turning on irrigation switch."""

    responses.extend(
        [mock_response(AVAILABLE_STATIONS_RESPONSE), mock_response(ZONE_OFF_RESPONSE)]
    )
    assert await setup_integration()

    # Initially all zones are off. Pick zone3 as an arbitrary to assert
    # state, then update below as a switch.
    zone = hass.states.get("switch.sprinkler_3")
    assert zone is not None
    assert zone.state == "off"

    aioclient_mock.mock_calls.clear()
    responses.extend(
        [
            mock_response(ACK_ECHO),  # Switch on response
            mock_response(ZONE_3_ON_RESPONSE),  # Updated zone state
        ]
    )
    await switch_common.async_turn_on(hass, "switch.sprinkler_3")
    await hass.async_block_till_done()
    assert len(aioclient_mock.mock_calls) == 2
    aioclient_mock.mock_calls.clear()

    # Verify switch state is updated
    zone = hass.states.get("switch.sprinkler_3")
    assert zone is not None
    assert zone.state == "on"


async def test_switch_off(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
) -> None:
    """Test turning off irrigation switch."""

    responses.extend(
        [mock_response(AVAILABLE_STATIONS_RESPONSE), mock_response(ZONE_3_ON_RESPONSE)]
    )
    assert await setup_integration()

    # Initially the test zone is on
    zone = hass.states.get("switch.sprinkler_3")
    assert zone is not None
    assert zone.state == "on"

    aioclient_mock.mock_calls.clear()
    responses.extend(
        [
            mock_response(ACK_ECHO),  # Switch off response
            mock_response(ZONE_OFF_RESPONSE),  # Updated zone state
        ]
    )
    await switch_common.async_turn_off(hass, "switch.sprinkler_3")
    await hass.async_block_till_done()

    # One call to change the service and one to refresh state
    assert len(aioclient_mock.mock_calls) == 2

    # Verify switch state is updated
    zone = hass.states.get("switch.sprinkler_3")
    assert zone is not None
    assert zone.state == "off"


async def test_irrigation_service(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
) -> None:
    """Test calling the irrigation service."""

    responses.extend(
        [mock_response(AVAILABLE_STATIONS_RESPONSE), mock_response(ZONE_3_ON_RESPONSE)]
    )
    assert await setup_integration()

    aioclient_mock.mock_calls.clear()
    responses.extend([mock_response(ACK_ECHO), mock_response(ZONE_OFF_RESPONSE)])

    await hass.services.async_call(
        DOMAIN,
        "start_irrigation",
        {ATTR_ENTITY_ID: "switch.sprinkler_5", "duration": 30},
        blocking=True,
    )

    # One call to change the service and one to refresh state
    assert len(aioclient_mock.mock_calls) == 2


async def test_rain_delay_service(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
) -> None:
    """Test calling the rain delay service."""

    responses.extend(
        [mock_response(AVAILABLE_STATIONS_RESPONSE), mock_response(ZONE_3_ON_RESPONSE)]
    )
    assert await setup_integration()

    aioclient_mock.mock_calls.clear()
    responses.extend(
        [
            mock_response(ACK_ECHO),
        ]
    )

    await hass.services.async_call(
        DOMAIN, "set_rain_delay", {"duration": 30}, blocking=True
    )

    assert len(aioclient_mock.mock_calls) == 1


async def test_platform_unavailable(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    responses: list[AiohttpClientMockResponse],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test failure while listing the stations when setting up the platform."""

    responses.append(
        AiohttpClientMockResponse("POST", URL, status=HTTPStatus.SERVICE_UNAVAILABLE)
    )

    with caplog.at_level(logging.WARNING):
        assert await setup_integration()

    assert "Failed to get stations" in caplog.text


async def test_coordinator_unavailable(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    responses: list[AiohttpClientMockResponse],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test failure to refresh the update coordinator."""

    responses.extend(
        [
            mock_response(AVAILABLE_STATIONS_RESPONSE),
            AiohttpClientMockResponse(
                "POST", URL, status=HTTPStatus.SERVICE_UNAVAILABLE
            ),
        ],
    )

    with caplog.at_level(logging.WARNING):
        assert await setup_integration()

    assert "Failed to load zone state" in caplog.text


@pytest.mark.parametrize(
    "yaml_config",
    [
        {
            DOMAIN: {
                "host": HOST,
                "password": PASSWORD,
                "trigger_time": 360,
                "zones": {
                    1: {
                        "friendly_name": "Garden Sprinkler",
                    },
                    2: {
                        "friendly_name": "Back Yard",
                    },
                },
            }
        },
    ],
)
async def test_yaml_config(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    responses: list[AiohttpClientMockResponse],
) -> None:
    """Test switch platform with fake data that creates 7 zones with one enabled."""

    responses.extend(
        [mock_response(AVAILABLE_STATIONS_RESPONSE), mock_response(ZONE_5_ON_RESPONSE)]
    )

    assert await setup_integration()

    assert hass.states.get("switch.garden_sprinkler")
    assert not hass.states.get("switch.sprinkler_1")
    assert hass.states.get("switch.back_yard")
    assert not hass.states.get("switch.sprinkler_2")
    assert hass.states.get("switch.sprinkler_3")
