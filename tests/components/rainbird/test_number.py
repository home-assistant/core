"""Tests for rainbird number platform."""

from http import HTTPStatus

import pytest

from homeassistant.components import number
from homeassistant.components.rainbird import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    ACK_ECHO,
    CONFIG_ENTRY_DATA_OLD_FORMAT,
    MAC_ADDRESS,
    RAIN_DELAY,
    RAIN_DELAY_OFF,
    mock_response,
    mock_response_error,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.NUMBER]


@pytest.fixture(autouse=True)
async def setup_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> list[Platform]:
    """Fixture to setup the config entry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("rain_delay_response", "expected_state"),
    [(RAIN_DELAY, "16"), (RAIN_DELAY_OFF, "0")],
)
async def test_number_values(
    hass: HomeAssistant,
    expected_state: str,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test number platform."""

    raindelay = hass.states.get("number.rain_bird_controller_rain_delay")
    assert raindelay is not None
    assert raindelay.state == expected_state
    assert raindelay.attributes == {
        "friendly_name": "Rain Bird Controller Rain delay",
        "min": 0,
        "max": 14,
        "mode": "auto",
        "step": 1,
        "unit_of_measurement": "d",
    }

    entity_entry = entity_registry.async_get("number.rain_bird_controller_rain_delay")
    assert entity_entry
    assert entity_entry.unique_id == "4c:a1:61:00:11:22-rain-delay"


async def test_set_value(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    aioclient_mock: AiohttpClientMocker,
    responses: list[str],
) -> None:
    """Test setting the rain delay number."""

    raindelay = hass.states.get("number.rain_bird_controller_rain_delay")
    assert raindelay is not None

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MAC_ADDRESS.lower())}
    )
    assert device
    assert device.name == "Rain Bird Controller"
    assert device.model == "ESP-TM2"
    assert device.sw_version == "9.12"

    aioclient_mock.mock_calls.clear()
    responses.append(mock_response(ACK_ECHO))

    await hass.services.async_call(
        number.DOMAIN,
        number.SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.rain_bird_controller_rain_delay",
            number.ATTR_VALUE: 3,
        },
        blocking=True,
    )

    assert len(aioclient_mock.mock_calls) == 1


@pytest.mark.parametrize(
    ("status", "expected_msg"),
    [
        (HTTPStatus.SERVICE_UNAVAILABLE, "Rain Bird device is busy"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, "Rain Bird device failure"),
    ],
)
async def test_set_value_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    responses: list[str],
    status: HTTPStatus,
    expected_msg: str,
) -> None:
    """Test an error while talking to the device."""

    aioclient_mock.mock_calls.clear()
    responses.append(mock_response_error(status=status))

    with pytest.raises(HomeAssistantError, match=expected_msg):
        await hass.services.async_call(
            number.DOMAIN,
            number.SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.rain_bird_controller_rain_delay",
                number.ATTR_VALUE: 3,
            },
            blocking=True,
        )

    assert len(aioclient_mock.mock_calls) == 1


@pytest.mark.parametrize(
    ("config_entry_data", "config_entry_unique_id", "setup_config_entry"),
    [
        (CONFIG_ENTRY_DATA_OLD_FORMAT, None, None),
    ],
)
async def test_no_unique_id(
    hass: HomeAssistant,
    responses: list[AiohttpClientMockResponse],
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test number platform with no unique id."""

    # Failure to migrate config entry to a unique id
    responses.insert(0, mock_response_error(HTTPStatus.SERVICE_UNAVAILABLE))

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    raindelay = hass.states.get("number.rain_bird_controller_rain_delay")
    assert raindelay is not None
    assert (
        raindelay.attributes.get("friendly_name") == "Rain Bird Controller Rain delay"
    )

    entity_entry = entity_registry.async_get("number.rain_bird_controller_rain_delay")
    assert not entity_entry
