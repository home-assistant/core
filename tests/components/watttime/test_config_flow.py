"""Test the WattTime config flow."""
from unittest.mock import AsyncMock, patch

from aiowatttime.errors import CoordinatesNotFoundError, InvalidCredentialsError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.watttime.config_flow import (
    CONF_LOCATION_TYPE,
    LOCATION_TYPE_COORDINATES,
    LOCATION_TYPE_HOME,
)
from homeassistant.components.watttime.const import (
    CONF_BALANCING_AUTHORITY,
    CONF_BALANCING_AUTHORITY_ABBREV,
    CONF_SHOW_ON_MAP,
    DOMAIN,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .conftest import (
    TEST_BALANCING_AUTHORITY,
    TEST_BALANCING_AUTHORITY_ABBREV,
    TEST_LATITUDE,
    TEST_LONGITUDE,
    TEST_PASSWORD,
    TEST_USERNAME,
)


@pytest.mark.parametrize(
    ("login_response", "login_errors"),
    [
        (AsyncMock(side_effect=Exception), {"base": "unknown"}),
        (AsyncMock(side_effect=InvalidCredentialsError), {"base": "invalid_auth"}),
    ],
)
@pytest.mark.parametrize(
    ("get_grid_region_response", "get_grid_region_errors"),
    [
        (
            AsyncMock(side_effect=CoordinatesNotFoundError),
            {"base": "unknown_coordinates"},
        ),
        (AsyncMock(side_effect=Exception), {"base": "unknown"}),
    ],
)
async def test_create_entry(
    hass: HomeAssistant,
    client,
    config_auth,
    config_coordinates,
    get_grid_region_errors,
    get_grid_region_response,
    login_errors,
    login_response,
    mock_aiowatttime,
) -> None:
    """Test creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test errors that can arise during login:
    with patch(
        "homeassistant.components.watttime.config_flow.Client.async_login",
        login_response,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=config_auth
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == login_errors

    # Test that we can recover from login errors:
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config_auth
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "location"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_LOCATION_TYPE: LOCATION_TYPE_COORDINATES}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "coordinates"

    # Test errors that can arise when selecting a location:
    with patch.object(
        client.emissions, "async_get_grid_region", get_grid_region_response
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=config_coordinates
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "coordinates"
        assert result["errors"] == get_grid_region_errors

    # Test that we can recover from location errors:
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config_coordinates
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{TEST_LATITUDE}, {TEST_LONGITUDE}"
    assert result["data"] == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
        CONF_BALANCING_AUTHORITY: TEST_BALANCING_AUTHORITY,
        CONF_BALANCING_AUTHORITY_ABBREV: TEST_BALANCING_AUTHORITY_ABBREV,
    }


async def test_duplicate_error(
    hass: HomeAssistant, config_auth, config_entry, setup_config_entry
) -> None:
    """Test that errors are shown when duplicate entries are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=config_auth
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_LOCATION_TYPE: LOCATION_TYPE_HOME}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant, config_entry, setup_config_entry
) -> None:
    """Test config flow options."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_SHOW_ON_MAP: False}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_SHOW_ON_MAP: False}


async def test_step_reauth(
    hass: HomeAssistant,
    config_auth,
    config_coordinates,
    config_entry,
    setup_config_entry,
) -> None:
    """Test a full reauth flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH},
        data={
            **config_auth,
            **config_coordinates,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "password"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1
