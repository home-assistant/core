"""Test the Ridwell config flow."""
from unittest.mock import AsyncMock, patch

from aioridwell.errors import InvalidCredentialsError, RidwellError
import pytest

from homeassistant import config_entries
from homeassistant.components.ridwell.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="client")
def client_fixture():
    """Define a fixture for an aioridwell client."""
    return AsyncMock(return_value=None)


@pytest.fixture(name="client_login")
def client_login_fixture(client):
    """Define a fixture for patching the aioridwell coroutine to get a client."""
    with patch(
        "homeassistant.components.ridwell.config_flow.async_get_client"
    ) as mock_client:
        mock_client.side_effect = client
        yield mock_client


async def test_duplicate_error(hass: HomeAssistant):
    """Test that errors are shown when duplicate entries are added."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@email.com",
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_show_form_user(hass: HomeAssistant) -> None:
    """Test showing the form to input credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None


async def test_step_reauth(hass: HomeAssistant, client_login) -> None:
    """Test a full reauth flow."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@email.com",
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.ridwell.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_REAUTH},
            data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1


async def test_step_user(hass: HomeAssistant, client_login) -> None:
    """Test that the full user step succeeds."""
    with patch(
        "homeassistant.components.ridwell.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY


@pytest.mark.parametrize(
    "client",
    [AsyncMock(side_effect=InvalidCredentialsError)],
)
async def test_step_user_invalid_credentials(hass: HomeAssistant, client_login) -> None:
    """Test that invalid credentials are handled correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.parametrize(
    "client",
    [AsyncMock(side_effect=RidwellError)],
)
async def test_step_user_unknown_error(hass: HomeAssistant, client_login) -> None:
    """Test that an unknown Ridwell error is handled correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "unknown"}


# async def test_step_reauth_invalid_credentials(hass: HomeAssistant) -> None:
#     """Test that invalid credentials during reauth are handled."""
#     MockConfigEntry(
#         domain=DOMAIN,
#         unique_id="51.528308, -0.3817765",
#         data={
#             CONF_USERNAME: "user",
#             CONF_PASSWORD: "password",
#             CONF_LATITUDE: 51.528308,
#             CONF_LONGITUDE: -0.3817765,
#             CONF_BALANCING_AUTHORITY: "Authority 1",
#             CONF_BALANCING_AUTHORITY_ABBREV: "AUTH_1",
#         },
#     ).add_to_hass(hass)

#     with patch(
#         "homeassistant.components.watttime.config_flow.Client.async_login",
#         AsyncMock(side_effect=InvalidCredentialsError),
#     ):
#         result = await hass.config_entries.flow.async_init(
#             DOMAIN,
#             context={"source": config_entries.SOURCE_REAUTH},
#             data={
#                 CONF_USERNAME: "user",
#                 CONF_PASSWORD: "password",
#                 CONF_LATITUDE: 51.528308,
#                 CONF_LONGITUDE: -0.3817765,
#                 CONF_BALANCING_AUTHORITY: "Authority 1",
#                 CONF_BALANCING_AUTHORITY_ABBREV: "AUTH_1",
#             },
#         )
#         result = await hass.config_entries.flow.async_configure(
#             result["flow_id"],
#             user_input={CONF_PASSWORD: "password"},
#         )
#         await hass.async_block_till_done()

#     assert result["type"] == RESULT_TYPE_FORM
#     assert result["errors"] == {"base": "invalid_auth"}


# async def test_step_user_coordinates(hass: HomeAssistant, client_login) -> None:
#     """Test a full login flow (inputting custom coordinates)."""

#     with patch(
#         "homeassistant.components.watttime.async_setup_entry",
#         return_value=True,
#     ):
#         result = await hass.config_entries.flow.async_init(
#             DOMAIN,
#             context={"source": config_entries.SOURCE_USER},
#             data={CONF_USERNAME: "user", CONF_PASSWORD: "password"},
#         )
#         result = await hass.config_entries.flow.async_configure(
#             result["flow_id"],
#             user_input={CONF_LOCATION_TYPE: LOCATION_TYPE_COORDINATES},
#         )
#         result = await hass.config_entries.flow.async_configure(
#             result["flow_id"],
#             user_input={CONF_LATITUDE: "51.528308", CONF_LONGITUDE: "-0.3817765"},
#         )
#         await hass.async_block_till_done()

#     assert result["type"] == RESULT_TYPE_CREATE_ENTRY
#     assert result["title"] == "51.528308, -0.3817765"
#     assert result["data"] == {
#         CONF_USERNAME: "user",
#         CONF_PASSWORD: "password",
#         CONF_LATITUDE: 51.528308,
#         CONF_LONGITUDE: -0.3817765,
#         CONF_BALANCING_AUTHORITY: "Authority 1",
#         CONF_BALANCING_AUTHORITY_ABBREV: "AUTH_1",
#     }


# async def test_step_user_home(hass: HomeAssistant, client_login) -> None:
#     """Test a full login flow (selecting the home location)."""

#     with patch(
#         "homeassistant.components.watttime.async_setup_entry",
#         return_value=True,
#     ):
#         result = await hass.config_entries.flow.async_init(
#             DOMAIN,
#             context={"source": config_entries.SOURCE_USER},
#             data={CONF_USERNAME: "user", CONF_PASSWORD: "password"},
#         )
#         result = await hass.config_entries.flow.async_configure(
#             result["flow_id"],
#             user_input={CONF_LOCATION_TYPE: LOCATION_TYPE_HOME},
#         )
#         await hass.async_block_till_done()

#     assert result["type"] == RESULT_TYPE_CREATE_ENTRY
#     assert result["title"] == "32.87336, -117.22743"
#     assert result["data"] == {
#         CONF_USERNAME: "user",
#         CONF_PASSWORD: "password",
#         CONF_LATITUDE: 32.87336,
#         CONF_LONGITUDE: -117.22743,
#         CONF_BALANCING_AUTHORITY: "Authority 1",
#         CONF_BALANCING_AUTHORITY_ABBREV: "AUTH_1",
#     }


# async def test_step_user_invalid_credentials(hass: HomeAssistant) -> None:
#     """Test that invalid credentials are handled."""

#     with patch(
#         "homeassistant.components.watttime.config_flow.Client.async_login",
#         AsyncMock(side_effect=InvalidCredentialsError),
#     ):
#         result = await hass.config_entries.flow.async_init(
#             DOMAIN,
#             context={"source": config_entries.SOURCE_USER},
#             data={CONF_USERNAME: "user", CONF_PASSWORD: "password"},
#         )
#         await hass.async_block_till_done()

#     assert result["type"] == RESULT_TYPE_FORM
#     assert result["errors"] == {"base": "invalid_auth"}


# @pytest.mark.parametrize("get_grid_region", [AsyncMock(side_effect=Exception)])
# async def test_step_user_unknown_error(hass: HomeAssistant, client_login) -> None:
#     """Test that an unknown error during the login step is handled."""

#     with patch(
#         "homeassistant.components.watttime.config_flow.Client.async_login",
#         AsyncMock(side_effect=Exception),
#     ):
#         result = await hass.config_entries.flow.async_init(
#             DOMAIN,
#             context={"source": config_entries.SOURCE_USER},
#             data={CONF_USERNAME: "user", CONF_PASSWORD: "password"},
#         )
#         await hass.async_block_till_done()

#     assert result["type"] == RESULT_TYPE_FORM
#     assert result["errors"] == {"base": "unknown"}
