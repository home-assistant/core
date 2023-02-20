"""Define tests for the AirVisual config flow."""
from unittest.mock import AsyncMock, patch

from pyairvisual.cloud_api import (
    InvalidKeyError,
    KeyExpiredError,
    NotFoundError,
    UnauthorizedError,
)
from pyairvisual.errors import AirVisualError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.airvisual import (
    CONF_CITY,
    CONF_INTEGRATION_TYPE,
    DOMAIN,
    INTEGRATION_TYPE_GEOGRAPHY_COORDS,
    INTEGRATION_TYPE_GEOGRAPHY_NAME,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant

from .conftest import (
    COORDS_CONFIG,
    NAME_CONFIG,
    TEST_CITY,
    TEST_COUNTRY,
    TEST_LATITUDE,
    TEST_LONGITUDE,
    TEST_STATE,
)


@pytest.mark.parametrize(
    ("integration_type", "input_form_step", "patched_method", "config", "entry_title"),
    [
        (
            INTEGRATION_TYPE_GEOGRAPHY_COORDS,
            "geography_by_coords",
            "nearest_city",
            COORDS_CONFIG,
            f"Cloud API ({TEST_LATITUDE}, {TEST_LONGITUDE})",
        ),
        (
            INTEGRATION_TYPE_GEOGRAPHY_NAME,
            "geography_by_name",
            "city",
            NAME_CONFIG,
            f"Cloud API ({TEST_CITY}, {TEST_STATE}, {TEST_COUNTRY})",
        ),
    ],
)
@pytest.mark.parametrize(
    ("response", "errors"),
    [
        (AsyncMock(side_effect=AirVisualError), {"base": "unknown"}),
        (AsyncMock(side_effect=InvalidKeyError), {CONF_API_KEY: "invalid_api_key"}),
        (AsyncMock(side_effect=KeyExpiredError), {CONF_API_KEY: "invalid_api_key"}),
        (AsyncMock(side_effect=NotFoundError), {CONF_CITY: "location_not_found"}),
        (AsyncMock(side_effect=UnauthorizedError), {CONF_API_KEY: "invalid_api_key"}),
    ],
)
async def test_create_entry(
    hass: HomeAssistant,
    cloud_api,
    config,
    entry_title,
    errors,
    input_form_step,
    integration_type,
    mock_pyairvisual,
    patched_method,
    response,
) -> None:
    """Test creating a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={"type": integration_type}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == input_form_step

    # Test errors that can arise:
    with patch.object(cloud_api.air_quality, patched_method, response):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=config
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == errors

    # Test that we can recover and finish the flow after errors occur:
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == entry_title
    assert result["data"] == {**config, CONF_INTEGRATION_TYPE: integration_type}


async def test_duplicate_error(hass: HomeAssistant, config, setup_config_entry) -> None:
    """Test that errors are shown when duplicate entries are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={"type": INTEGRATION_TYPE_GEOGRAPHY_COORDS},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "geography_by_coords"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
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
    hass: HomeAssistant, config_entry, setup_config_entry
) -> None:
    """Test that the reauth step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH}, data=config_entry.data
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    new_api_key = "defgh67890"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: new_api_key}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    assert hass.config_entries.async_entries()[0].data[CONF_API_KEY] == new_api_key
