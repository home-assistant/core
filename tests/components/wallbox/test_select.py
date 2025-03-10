"""Test Wallbox Select component."""

import pytest
import requests_mock

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.wallbox.const import (
    CHARGER_DATA_KEY,
    CHARGER_ECO_SMART_KEY,
    CHARGER_ECO_SMART_MODE_KEY,
    CHARGER_STATUS_ID_KEY,
    EcoSmartMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, HomeAssistantError

from . import (
    authorisation_response,
    setup_integration_select,
    test_response,
    test_response_eco_mode,
    test_response_full_solar,
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

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )

        mock_request.put(
            "https://api.wall-box.com/v4/chargers/12345/eco-smart",
            json={
                CHARGER_DATA_KEY: {
                    CHARGER_ECO_SMART_KEY: 1,
                    CHARGER_ECO_SMART_MODE_KEY: 0,
                }
            },
            status_code=200,
        )

        state = hass.states.get(MOCK_SELECT_ENTITY_ID)
        assert state
        assert state.state == mode

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                ATTR_OPTION: EcoSmartMode.ECO_MODE,
            },
            blocking=True,
        )
        await hass.async_block_till_done()


@pytest.mark.parametrize(("mode", "response"), TEST_OPTIONS)
async def test_wallbox_select_class_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry, mode, response
) -> None:
    """Test wallbox select class connection error."""

    await setup_integration_select(hass, entry, response)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.put(
            "https://api.wall-box.com/v4/chargers/12345/eco-smart",
            json={CHARGER_STATUS_ID_KEY: 193},
            status_code=404,
        )

        with pytest.raises(HomeAssistantError):
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

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.put(
            "https://api.wall-box.com/v4/chargers/12345/eco-smart",
            json={CHARGER_STATUS_ID_KEY: 193},
            status_code=403,
        )

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                SELECT_DOMAIN,
                SERVICE_SELECT_OPTION,
                {
                    ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                    ATTR_OPTION: mode,
                },
                blocking=True,
            )
