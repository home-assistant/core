"""Test the Environment Canada (EC) config flow."""
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import aiohttp
import pytest
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.environment_canada.const import (
    CONF_LANGUAGE,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

from tests.common import MockConfigEntry


def mocked_ec(
    station_id="ON/s1234567", lat=42.5, lon=54.2, lang="English", update=None
):
    """Mock the env_canada library."""
    ec_mock = MagicMock()
    type(ec_mock).station_id = PropertyMock(return_value=station_id)
    type(ec_mock).latitude = PropertyMock(return_value=lat)
    type(ec_mock).longitude = PropertyMock(return_value=lon)
    type(ec_mock).language = PropertyMock(return_value=lang)

    if update:
        ec_mock.update = update
    else:
        ec_mock.update = AsyncMock(return_value=Mock(settings=True))

    return patch(
        "homeassistant.components.environment_canada.config_flow.ECWeather",
        return_value=ec_mock,
    )


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with mocked_ec(), patch(
        "homeassistant.components.environment_canada.async_setup_entry",
        return_value=True,
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert flow["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert flow["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {
                CONF_STATION: "ON/s1234567",
                CONF_LATITUDE: 42.5,
                CONF_LONGITUDE: 54.2,
                CONF_LANGUAGE: "English",
            },
        )
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {CONF_NAME: "SomePlace"},
        )
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {
            "station": "ON/s1234567",
            "latitude": 42.5,
            "longitude": 54.2,
            "language": "English",
            "name": "SomePlace",
        }
        assert result["title"] == "SomePlace"
        assert flow["errors"] == {}


async def test_create_same_entry_twice(hass):
    """Test duplicate entries."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STATION: "ON/s1234567", CONF_LANGUAGE: "English"},
    )
    entry.add_to_hass(hass)

    with mocked_ec(), patch(
        "homeassistant.components.environment_canada.async_setup_entry",
        return_value=True,
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {
                CONF_STATION: "ON/s1234567",
                CONF_LATITUDE: 42.5,
                CONF_LONGITUDE: 54.2,
                CONF_LANGUAGE: "English",
            },
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "already_configured"}


async def test_bad_station_id(hass):
    """Test duplicate station id."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with mocked_ec(station_id=None), patch(
        "homeassistant.components.environment_canada.async_setup_entry",
        return_value=True,
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {},
        )
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "bad_station_id"}


@pytest.mark.parametrize(
    "error",
    [
        (aiohttp.ClientResponseError(Mock(), (), status=404), "bad_station_id"),
        (aiohttp.ClientResponseError(Mock(), (), status=400), "error_response"),
        (aiohttp.ClientConnectionError, "cannot_connect"),
        (vol.error.MultipleInvalid, "config_error"),
        (ValueError, "unknown"),
    ],
)
async def test_exception_handling(hass, error):
    """Test exception handling."""
    exc, base_error = error
    await setup.async_setup_component(hass, "persistent_notification", {})

    with mocked_ec(update=AsyncMock(side_effect=exc)), patch(
        "homeassistant.components.environment_canada.async_setup_entry",
        return_value=True,
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {},
        )
        await hass.async_block_till_done()
        assert result["type"] == "form"
        assert result["errors"] == {"base": base_error}
