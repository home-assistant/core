"""Test Wallbox Select component."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.wallbox.const import CHARGER_STATUS_ID_KEY, EcoSmartMode
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, HomeAssistantError

from . import (
    authorisation_response,
    http_404_error,
    setup_integration_select,
    test_response,
    test_response_eco_mode,
    test_response_full_solar,
    test_response_no_power_boost,
)
from .const import MOCK_SELECT_ENTITY_ID

from tests.common import MockConfigEntry

TEST_OPTIONS = [
    (EcoSmartMode.OFF, test_response),
    (EcoSmartMode.ECO_MODE, test_response_eco_mode),
    (EcoSmartMode.FULL_SOLAR, test_response_full_solar),
]


@pytest.mark.parametrize(("mode", "response"), TEST_OPTIONS)
async def test_wallbox_select_solar_charging_class(
    hass: HomeAssistant, entry: MockConfigEntry, mode, response
) -> None:
    """Test wallbox select class."""

    await setup_integration_select(hass, entry, response)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.enableEcoSmart",
            new=Mock(return_value={CHARGER_STATUS_ID_KEY: 193}),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.disableEcoSmart",
            new=Mock(return_value={CHARGER_STATUS_ID_KEY: 193}),
        ),
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

        state = hass.states.get(MOCK_SELECT_ENTITY_ID)
        assert state.state == mode


async def test_wallbox_select_no_power_boost_class(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox select class."""

    await setup_integration_select(hass, entry, test_response_no_power_boost)

    state = hass.states.get(MOCK_SELECT_ENTITY_ID)
    assert state is None


@pytest.mark.parametrize(("mode", "response"), TEST_OPTIONS)
async def test_wallbox_select_class_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry, mode, response
) -> None:
    """Test wallbox select class connection error."""

    await setup_integration_select(hass, entry, response)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.disableEcoSmart",
            new=Mock(side_effect=http_404_error),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.enableEcoSmart",
            new=Mock(side_effect=http_404_error),
        ),
        pytest.raises(HomeAssistantError, match="Error communicating with Wallbox API"),
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
async def test_wallbox_select_class_authentication_error(
    hass: HomeAssistant, entry: MockConfigEntry, mode, response
) -> None:
    """Test wallbox select class authentication error."""

    await setup_integration_select(hass, entry, response)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.disableEcoSmart",
            new=Mock(side_effect=ConnectionError),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.enableEcoSmart",
            new=Mock(side_effect=ConnectionError),
        ),
        pytest.raises(HomeAssistantError, match="Error communicating with Wallbox API"),
    ):
        # Test behavior when a connection error occurs
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                ATTR_OPTION: mode,
            },
            blocking=True,
        )
