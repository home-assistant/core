"""Test the WattTime config flow."""
from unittest.mock import AsyncMock, patch

from aiowatttime.errors import CoordinatesNotFoundError, InvalidCredentialsError
import pytest

from homeassistant import config_entries, setup
from homeassistant.components.watttime.config_flow import (
    CONF_LOCATION_TYPE,
    LOCATION_TYPE_COORDINATES,
    LOCATION_TYPE_HOME,
)
from homeassistant.components.watttime.const import (
    CONF_BALANCING_AUTHORITY,
    CONF_BALANCING_AUTHORITY_ABBREV,
    DOMAIN,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="client")
def client_fixture(get_grid_region):
    """Define a fixture for an aiowatttime client."""
    client = AsyncMock(return_value=None)
    client.emissions.async_get_grid_region = get_grid_region
    return client


@pytest.fixture(name="client_login")
def client_login_fixture(client):
    """Define a fixture for patching the aiowatttime coroutine to get a client."""
    with patch("homeassistant.components.watttime.config_flow.Client.async_login") as m:
        m.return_value = client
        yield m


@pytest.fixture(name="get_grid_region")
def get_grid_region_fixture():
    """Define a fixture for getting grid region data."""
    return AsyncMock(return_value={"abbrev": "AUTH_1", "id": 1, "name": "Authority 1"})


async def test_duplicate_error(hass: HomeAssistant, client_login):
    """Test that errors are shown when duplicate entries are added."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="32.87336, -117.22743",
        data={
            CONF_USERNAME: "user",
            CONF_PASSWORD: "password",
            CONF_LATITUDE: 32.87336,
            CONF_LONGITUDE: -117.22743,
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "user", CONF_PASSWORD: "password"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION_TYPE: LOCATION_TYPE_HOME},
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_show_form_coordinates(hass: HomeAssistant) -> None:
    """Test showing the form to input custom latitude/longitude."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: "user", CONF_PASSWORD: "password"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION_TYPE: LOCATION_TYPE_COORDINATES},
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "coordinates"
    assert result["errors"] is None


async def test_show_form_user(hass: HomeAssistant) -> None:
    """Test showing the form to select the authentication type."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None


@pytest.mark.parametrize(
    "get_grid_region", [AsyncMock(side_effect=CoordinatesNotFoundError)]
)
async def test_step_coordinates_unknown_coordinates(
    hass: HomeAssistant, client_login
) -> None:
    """Test that providing coordinates with no data is handled."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "user", CONF_PASSWORD: "password"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION_TYPE: LOCATION_TYPE_COORDINATES},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LATITUDE: "0", CONF_LONGITUDE: "0"},
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"latitude": "unknown_coordinates"}


@pytest.mark.parametrize("get_grid_region", [AsyncMock(side_effect=Exception)])
async def test_step_coordinates_unknown_error(
    hass: HomeAssistant, client_login
) -> None:
    """Test that providing coordinates with no data is handled."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "user", CONF_PASSWORD: "password"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION_TYPE: LOCATION_TYPE_HOME},
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "unknown"}


async def test_step_login_coordinates(hass: HomeAssistant, client_login) -> None:
    """Test a full login flow (inputting custom coordinates)."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "homeassistant.components.watttime.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_USERNAME: "user", CONF_PASSWORD: "password"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_LOCATION_TYPE: LOCATION_TYPE_COORDINATES},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_LATITUDE: "51.528308", CONF_LONGITUDE: "-0.3817765"},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "51.528308, -0.3817765"
    assert result["data"] == {
        CONF_USERNAME: "user",
        CONF_PASSWORD: "password",
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
        CONF_BALANCING_AUTHORITY: "Authority 1",
        CONF_BALANCING_AUTHORITY_ABBREV: "AUTH_1",
    }


async def test_step_user_home(hass: HomeAssistant, client_login) -> None:
    """Test a full login flow (selecting the home location)."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "homeassistant.components.watttime.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_USERNAME: "user", CONF_PASSWORD: "password"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_LOCATION_TYPE: LOCATION_TYPE_HOME},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "32.87336, -117.22743"
    assert result["data"] == {
        CONF_USERNAME: "user",
        CONF_PASSWORD: "password",
        CONF_LATITUDE: 32.87336,
        CONF_LONGITUDE: -117.22743,
        CONF_BALANCING_AUTHORITY: "Authority 1",
        CONF_BALANCING_AUTHORITY_ABBREV: "AUTH_1",
    }


async def test_step_user_invalid_credentials(hass: HomeAssistant) -> None:
    """Test that invalid credentials are handled."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "homeassistant.components.watttime.config_flow.Client.async_login",
        AsyncMock(side_effect=InvalidCredentialsError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_USERNAME: "user", CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"username": "invalid_auth"}


@pytest.mark.parametrize("get_grid_region", [AsyncMock(side_effect=Exception)])
async def test_step_user_unknown_error(hass: HomeAssistant, client_login) -> None:
    """Test that an unknown error during the login step is handled."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "homeassistant.components.watttime.config_flow.Client.async_login",
        AsyncMock(side_effect=Exception),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_USERNAME: "user", CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "unknown"}
