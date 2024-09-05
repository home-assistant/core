"""Test Wallbox Switch component."""

import json

import pytest
import requests_mock

from homeassistant.components.input_number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.wallbox import InvalidAuth
from homeassistant.components.wallbox.const import (
    CHARGER_ENERGY_PRICE_KEY,
    CHARGER_MAX_CHARGING_CURRENT_KEY,
    CHARGER_MAX_ICP_CURRENT_KEY,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from . import (
    authorisation_response,
    setup_integration,
    setup_integration_bidir,
    setup_integration_platform_not_ready,
)
from .const import (
    MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
    MOCK_NUMBER_ENTITY_ICP_CURRENT_ID,
    MOCK_NUMBER_ENTITY_ID,
)

from tests.common import MockConfigEntry


async def test_wallbox_number_class(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json=json.loads(json.dumps({CHARGER_MAX_CHARGING_CURRENT_KEY: 20})),
            status_code=200,
        )
        state = hass.states.get(MOCK_NUMBER_ENTITY_ID)
        assert state.attributes["min"] == 6
        assert state.attributes["max"] == 25

        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ID,
                ATTR_VALUE: 20,
            },
            blocking=True,
        )
    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_number_class_bidir(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration_bidir(hass, entry)

    state = hass.states.get(MOCK_NUMBER_ENTITY_ID)
    assert state.attributes["min"] == -25
    assert state.attributes["max"] == 25
    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_number_energy_class(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )

        mock_request.post(
            "https://api.wall-box.com/chargers/config/12345",
            json=json.loads(json.dumps({CHARGER_ENERGY_PRICE_KEY: 1.1})),
            status_code=200,
        )

        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
                ATTR_VALUE: 1.1,
            },
            blocking=True,
        )
    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_number_class_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json=json.loads(json.dumps({CHARGER_MAX_CHARGING_CURRENT_KEY: 20})),
            status_code=404,
        )

        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                "number",
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ID,
                    ATTR_VALUE: 20,
                },
                blocking=True,
            )
    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_number_class_energy_price_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.post(
            "https://api.wall-box.com/chargers/config/12345",
            json=json.loads(json.dumps({CHARGER_ENERGY_PRICE_KEY: 1.1})),
            status_code=404,
        )

        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                "number",
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
                    ATTR_VALUE: 1.1,
                },
                blocking=True,
            )
    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_number_class_energy_price_auth_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.post(
            "https://api.wall-box.com/chargers/config/12345",
            json=json.loads(json.dumps({CHARGER_ENERGY_PRICE_KEY: 1.1})),
            status_code=403,
        )

        with pytest.raises(ConfigEntryAuthFailed):
            await hass.services.async_call(
                "number",
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
                    ATTR_VALUE: 1.1,
                },
                blocking=True,
            )
    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_number_class_platform_not_ready(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox lock not loaded on authentication error."""

    await setup_integration_platform_not_ready(hass, entry)

    state = hass.states.get(MOCK_NUMBER_ENTITY_ID)

    assert state is None

    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_number_class_icp_energy(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )

        mock_request.post(
            "https://api.wall-box.com/chargers/config/12345",
            json={CHARGER_MAX_ICP_CURRENT_KEY: 10},
            status_code=200,
        )

        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ICP_CURRENT_ID,
                ATTR_VALUE: 10,
            },
            blocking=True,
        )
    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_number_class_icp_energy_auth_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.post(
            "https://api.wall-box.com/chargers/config/12345",
            json={CHARGER_MAX_ICP_CURRENT_KEY: 10},
            status_code=403,
        )

        with pytest.raises(InvalidAuth):
            await hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ICP_CURRENT_ID,
                    ATTR_VALUE: 10,
                },
                blocking=True,
            )
    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_number_class_icp_energy_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.post(
            "https://api.wall-box.com/chargers/config/12345",
            json={CHARGER_MAX_ICP_CURRENT_KEY: 10},
            status_code=404,
        )

        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ICP_CURRENT_ID,
                    ATTR_VALUE: 10,
                },
                blocking=True,
            )
    await hass.config_entries.async_unload(entry.entry_id)
