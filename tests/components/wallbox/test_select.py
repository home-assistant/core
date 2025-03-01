"""Test Wallbox Select component."""

import pytest
import requests_mock

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.wallbox.const import CHARGER_STATUS_ID_KEY, EcoSmartMode
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from . import authorisation_response, setup_integration
from .const import MOCK_SELECT_ENTITY_ID

from tests.common import MockConfigEntry


async def test_wallbox_select_class(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox select class."""

    await setup_integration(hass, entry)

    state = hass.states.get(MOCK_SELECT_ENTITY_ID)
    assert state
    assert state.state == EcoSmartMode.OFF

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.put(
            "https://api.wall-box.com/v4/chargers/12345/eco-smart",
            json={CHARGER_STATUS_ID_KEY: 193},
            status_code=200,
        )

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                ATTR_OPTION: EcoSmartMode.ECO_MODE,
            },
            blocking=True,
        )

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                ATTR_OPTION: EcoSmartMode.FULL_SOLAR,
            },
            blocking=True,
        )

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                ATTR_OPTION: EcoSmartMode.OFF,
            },
            blocking=True,
        )


async def test_wallbox_select_class_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox select class connection error."""

    await setup_integration(hass, entry)

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

        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                SELECT_DOMAIN,
                SERVICE_SELECT_OPTION,
                {
                    ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                    ATTR_OPTION: EcoSmartMode.ECO_MODE,
                },
                blocking=True,
            )

        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                SELECT_DOMAIN,
                SERVICE_SELECT_OPTION,
                {
                    ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                    ATTR_OPTION: EcoSmartMode.FULL_SOLAR,
                },
                blocking=True,
            )

        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                SELECT_DOMAIN,
                SERVICE_SELECT_OPTION,
                {
                    ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                    ATTR_OPTION: EcoSmartMode.OFF,
                },
                blocking=True,
            )


async def test_wallbox_select_class_authentication_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox select class authentication error."""

    await setup_integration(hass, entry)

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

        with pytest.raises(ConfigEntryAuthFailed):
            await hass.services.async_call(
                SELECT_DOMAIN,
                SERVICE_SELECT_OPTION,
                {
                    ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                    ATTR_OPTION: EcoSmartMode.ECO_MODE,
                },
                blocking=True,
            )

        with pytest.raises(ConfigEntryAuthFailed):
            await hass.services.async_call(
                SELECT_DOMAIN,
                SERVICE_SELECT_OPTION,
                {
                    ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                    ATTR_OPTION: EcoSmartMode.FULL_SOLAR,
                },
                blocking=True,
            )

        with pytest.raises(ConfigEntryAuthFailed):
            await hass.services.async_call(
                SELECT_DOMAIN,
                SERVICE_SELECT_OPTION,
                {
                    ATTR_ENTITY_ID: MOCK_SELECT_ENTITY_ID,
                    ATTR_OPTION: EcoSmartMode.OFF,
                },
                blocking=True,
            )
