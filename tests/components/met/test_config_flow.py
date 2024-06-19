"""Tests for Met.no config flow."""

from collections.abc import Generator
from typing import Any
from unittest.mock import ANY, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.met.const import DOMAIN, HOME_LOCATION_NAME
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import init_integration

from tests.common import MockConfigEntry


@pytest.fixture(name="met_setup", autouse=True)
def met_setup_fixture(request: pytest.FixtureRequest) -> Generator[Any]:
    """Patch met setup entry."""
    if "disable_autouse_fixture" in request.keywords:
        yield
    else:
        with patch("homeassistant.components.met.async_setup_entry", return_value=True):
            yield


async def test_show_config_form(hass: HomeAssistant) -> None:
    """Test show configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_flow_with_home_location(hass: HomeAssistant) -> None:
    """Test config flow.

    Test the flow when a default location is configured.
    Then it should return a form with default values.
    """
    hass.config.latitude = 1
    hass.config.longitude = 2
    hass.config.elevation = 3

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    default_data = result["data_schema"]({})
    assert default_data["name"] == HOME_LOCATION_NAME
    assert default_data["latitude"] == 1
    assert default_data["longitude"] == 2
    assert default_data["elevation"] == 3


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test create entry from user input."""
    test_data = {
        "name": "home",
        CONF_LONGITUDE: 0,
        CONF_LATITUDE: 0,
        CONF_ELEVATION: 0,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "home"
    assert result["data"] == test_data


async def test_flow_entry_already_exists(hass: HomeAssistant) -> None:
    """Test user input for config_entry that already exists.

    Test when the form should show when user puts existing location
    in the config gui. Then the form should show with error.
    """
    first_entry = MockConfigEntry(
        domain="met",
        data={"name": "home", CONF_LATITUDE: 0, CONF_LONGITUDE: 0, CONF_ELEVATION: 0},
    )
    first_entry.add_to_hass(hass)

    test_data = {
        "name": "home",
        CONF_LONGITUDE: 0,
        CONF_LATITUDE: 0,
        CONF_ELEVATION: 0,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["name"] == "already_configured"


async def test_onboarding_step(hass: HomeAssistant) -> None:
    """Test initializing via onboarding step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "onboarding"}, data={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOME_LOCATION_NAME
    assert result["data"] == {"track_home": True}


@pytest.mark.parametrize(
    ("latitude", "longitude"), [(52.3731339, 4.8903147), (0.0, 0.0)]
)
async def test_onboarding_step_abort_no_home(
    hass: HomeAssistant, latitude, longitude
) -> None:
    """Test entry not created when default step fails."""
    await async_process_ha_core_config(
        hass,
        {"latitude": latitude, "longitude": longitude},
    )

    assert hass.config.latitude == latitude
    assert hass.config.longitude == longitude

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "onboarding"}, data={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_home"


@pytest.mark.disable_autouse_fixture
async def test_options_flow(hass: HomeAssistant) -> None:
    """Test show options form."""
    update_data = {
        CONF_NAME: "test",
        CONF_LATITUDE: 12,
        CONF_LONGITUDE: 23,
        CONF_ELEVATION: 456,
    }

    entry = await init_integration(hass)
    await hass.async_block_till_done()

    # Test show Options form
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Test Options flow updated config entry
    with patch(
        "homeassistant.components.met.coordinator.metno.MetWeatherData"
    ) as weatherdatamock:
        result = await hass.config_entries.options.async_init(
            entry.entry_id, data=update_data
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mock Title"
    assert result["data"] == update_data
    weatherdatamock.assert_called_with(
        {"lat": "12", "lon": "23", "msl": "456"}, ANY, api_url=ANY
    )
