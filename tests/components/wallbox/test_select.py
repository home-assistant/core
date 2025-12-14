"""Test Wallbox Select component."""

from unittest.mock import patch

import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.wallbox.const import EcoSmartMode
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, HomeAssistantError

from .conftest import http_404_error, http_429_error, setup_integration
from .const import (
    MOCK_SELECT_ENTITY_ID,
    WALLBOX_STATUS_RESPONSE,
    WALLBOX_STATUS_RESPONSE_ECO_MODE,
    WALLBOX_STATUS_RESPONSE_FULL_SOLAR,
    WALLBOX_STATUS_RESPONSE_NO_POWER_BOOST,
)

from tests.common import MockConfigEntry

TEST_OPTIONS = [
    (EcoSmartMode.OFF, WALLBOX_STATUS_RESPONSE),
    (EcoSmartMode.ECO_MODE, WALLBOX_STATUS_RESPONSE_ECO_MODE),
    (EcoSmartMode.FULL_SOLAR, WALLBOX_STATUS_RESPONSE_FULL_SOLAR),
]


@pytest.mark.parametrize(("mode", "response"), TEST_OPTIONS)
async def test_wallbox_select_solar_charging_class(
    hass: HomeAssistant, entry: MockConfigEntry, mode, response, mock_wallbox
) -> None:
    """Test wallbox select class."""
    with patch.object(mock_wallbox, "getChargerStatus", return_value=response):
        await setup_integration(hass, entry)

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                ATTR_OPTION: mode,
            },
            blocking=True,
        )

        state = hass.states.get(MOCK_SELECT_ENTITY_ID)
        assert state.state == mode


async def test_wallbox_select_no_power_boost_class(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test wallbox select class."""

    with patch.object(
        mock_wallbox,
        "getChargerStatus",
        return_value=WALLBOX_STATUS_RESPONSE_NO_POWER_BOOST,
    ):
        await setup_integration(hass, entry)

        state = hass.states.get(MOCK_SELECT_ENTITY_ID)
        assert state is None


@pytest.mark.parametrize(("mode", "response"), TEST_OPTIONS)
async def test_wallbox_select_class_error(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mode,
    response,
    mock_wallbox,
) -> None:
    """Test wallbox select class connection error."""

    await setup_integration(hass, entry)

    with (
        patch.object(mock_wallbox, "getChargerStatus", return_value=response),
        patch.object(mock_wallbox, "disableEcoSmart", side_effect=http_404_error),
        patch.object(mock_wallbox, "enableEcoSmart", side_effect=http_404_error),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                ATTR_OPTION: mode,
            },
            blocking=True,
        )


@pytest.mark.parametrize(("mode", "response"), TEST_OPTIONS)
async def test_wallbox_select_too_many_requests_error(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mode,
    response,
    mock_wallbox,
) -> None:
    """Test wallbox select class connection error."""

    await setup_integration(hass, entry)

    with (
        patch.object(mock_wallbox, "getChargerStatus", return_value=response),
        patch.object(mock_wallbox, "disableEcoSmart", side_effect=http_429_error),
        patch.object(mock_wallbox, "enableEcoSmart", side_effect=http_429_error),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                ATTR_OPTION: mode,
            },
            blocking=True,
        )


@pytest.mark.parametrize(("mode", "response"), TEST_OPTIONS)
async def test_wallbox_select_connection_error(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mode,
    response,
    mock_wallbox,
) -> None:
    """Test wallbox select class connection error."""

    await setup_integration(hass, entry)

    with (
        patch.object(mock_wallbox, "getChargerStatus", return_value=response),
        patch.object(mock_wallbox, "disableEcoSmart", side_effect=ConnectionError),
        patch.object(mock_wallbox, "enableEcoSmart", side_effect=ConnectionError),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                ATTR_OPTION: mode,
            },
            blocking=True,
        )
