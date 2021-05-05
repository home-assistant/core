"""Tests for the Meteoclimatic config flow."""
from unittest.mock import patch

from meteoclimatic.exceptions import MeteoclimaticError, StationNotFound
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.meteoclimatic.const import CONF_STATION_CODE, DOMAIN
from homeassistant.config_entries import SOURCE_USER

from tests.common import MockConfigEntry

TEST_STATION_CODE = "ESCAT4300000043206B"
TEST_STATION_NAME = "Reus (Tarragona)"


@pytest.fixture(name="client")
def mock_controller_client():
    """Mock a successful client."""
    with patch(
        "homeassistant.components.meteoclimatic.config_flow.MeteoclimaticClient",
        update=False,
    ) as service_mock:
        service_mock.return_value.get_data.return_value = {
            "station_code": TEST_STATION_CODE
        }
        weather = service_mock.return_value.weather_at_station.return_value
        weather.station.name = TEST_STATION_NAME
        yield service_mock


@pytest.fixture(autouse=True)
def mock_setup():
    """Prevent setup."""
    with patch(
        "homeassistant.components.meteoclimatic.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_user(hass, client):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_STATION_CODE: TEST_STATION_CODE},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == TEST_STATION_CODE
    assert result["title"] == TEST_STATION_NAME
    assert result["data"][CONF_STATION_CODE] == TEST_STATION_CODE


async def test_abort_if_already_setup(hass, client):
    """Test we abort if already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STATION_CODE: TEST_STATION_CODE},
        unique_id=TEST_STATION_CODE,
    ).add_to_hass(hass)

    # Should fail, same station code (flow)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_STATION_CODE: TEST_STATION_CODE},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_not_found(hass):
    """Test when we have the station code is not found."""
    with patch(
        "homeassistant.components.meteoclimatic.config_flow.MeteoclimaticClient.weather_at_station",
        side_effect=StationNotFound(TEST_STATION_CODE),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_STATION_CODE: TEST_STATION_CODE},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "not_found"


async def test_unknown_error(hass):
    """Test when we have an unknown error fetching station data."""
    with patch(
        "homeassistant.components.meteoclimatic.config_flow.MeteoclimaticClient.weather_at_station",
        side_effect=MeteoclimaticError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_STATION_CODE: TEST_STATION_CODE},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "unknown"
