"""Test the CO2 Signal config flow."""

from typing import Any
from unittest.mock import AsyncMock, patch

from aioelectricitymaps import (
    ElectricityMapsConnectionError,
    ElectricityMapsError,
    ElectricityMapsInvalidTokenError,
    ElectricityMapsNoDataError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.co2signal import config_flow
from homeassistant.components.co2signal.const import DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_COUNTRY_CODE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.usefixtures("electricity_maps")
async def test_form_home(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.co2signal.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "location": config_flow.TYPE_USE_HOME,
                "api_key": "api_key",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Electricity Maps"
    assert result2["data"] == {
        "api_key": "api_key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("electricity_maps")
async def test_form_coordinates(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "location": config_flow.TYPE_SPECIFY_COORDINATES,
            "api_key": "api_key",
        },
    )
    assert result2["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.co2signal.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "latitude": 12.3,
                "longitude": 45.6,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "12.3, 45.6"
    assert result3["data"] == {
        "latitude": 12.3,
        "longitude": 45.6,
        "api_key": "api_key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("electricity_maps")
async def test_form_country(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "location": config_flow.TYPE_SPECIFY_COUNTRY,
            "api_key": "api_key",
        },
    )
    assert result2["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.co2signal.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "country_code": "fr",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "fr"
    assert result3["data"] == {
        "country_code": "fr",
        "api_key": "api_key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "err_code"),
    [
        (
            ElectricityMapsInvalidTokenError,
            "invalid_auth",
        ),
        (ElectricityMapsError("Something else"), "unknown"),
        (ElectricityMapsConnectionError("Boom"), "unknown"),
        (ElectricityMapsNoDataError("I have no data"), "no_data"),
    ],
    ids=["invalid auth", "generic error", "json decode error", "no data error"],
)
async def test_form_error_handling(
    hass: HomeAssistant,
    electricity_maps: AsyncMock,
    side_effect: Exception,
    err_code: str,
) -> None:
    """Test we handle expected errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    electricity_maps.carbon_intensity_for_home_assistant.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "location": config_flow.TYPE_USE_HOME,
            "api_key": "api_key",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": err_code}

    # reset mock and test if now succeeds
    electricity_maps.carbon_intensity_for_home_assistant.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "location": config_flow.TYPE_USE_HOME,
            "api_key": "api_key",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Electricity Maps"
    assert result["data"] == {
        "api_key": "api_key",
    }


async def test_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    electricity_maps: AsyncMock,
) -> None:
    """Test reauth flow."""
    config_entry.add_to_hass(hass)

    init_result = await config_entry.start_reauth_flow(hass)

    assert init_result["type"] is FlowResultType.FORM
    assert init_result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.co2signal.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        configure_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {
                CONF_API_KEY: "api_key2",
            },
        )
        await hass.async_block_till_done()

    assert configure_result["type"] is FlowResultType.ABORT
    assert configure_result["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1


def _suggested_values(result: ConfigFlowResult) -> dict[str, Any]:
    """Return the suggested values of a form."""
    return {
        str(key): (key.description or {}).get("suggested_value")
        for key in result["data_schema"].schema
    }


@pytest.mark.parametrize(
    ("entry_data", "location", "step_id", "step_input", "expected_data", "title"),
    [
        pytest.param(
            {CONF_API_KEY: "api_key"},
            config_flow.TYPE_SPECIFY_COORDINATES,
            "coordinates",
            {CONF_LATITUDE: 12.3, CONF_LONGITUDE: 45.6},
            {CONF_API_KEY: "api_key2", CONF_LATITUDE: 12.3, CONF_LONGITUDE: 45.6},
            "12.3, 45.6",
            id="home_to_coordinates",
        ),
        pytest.param(
            {CONF_API_KEY: "api_key", CONF_LATITUDE: 12.3, CONF_LONGITUDE: 45.6},
            config_flow.TYPE_SPECIFY_COUNTRY,
            "country",
            {CONF_COUNTRY_CODE: "fr"},
            {CONF_API_KEY: "api_key2", CONF_COUNTRY_CODE: "fr"},
            "fr",
            id="coordinates_to_country",
        ),
        pytest.param(
            {CONF_API_KEY: "api_key", CONF_COUNTRY_CODE: "fr"},
            config_flow.TYPE_SPECIFY_COORDINATES,
            "coordinates",
            {CONF_LATITUDE: 12.3, CONF_LONGITUDE: 45.6},
            {CONF_API_KEY: "api_key2", CONF_LATITUDE: 12.3, CONF_LONGITUDE: 45.6},
            "12.3, 45.6",
            id="country_to_coordinates",
        ),
    ],
)
@pytest.mark.usefixtures("electricity_maps")
async def test_reconfigure(
    hass: HomeAssistant,
    entry_data: dict[str, Any],
    location: str,
    step_id: str,
    step_input: dict[str, Any],
    expected_data: dict[str, Any],
    title: str,
) -> None:
    """Test reconfiguring the location and API key of an entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"location": location, CONF_API_KEY: "api_key2"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id

    with patch(
        "homeassistant.components.co2signal.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], step_input
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == expected_data
    assert config_entry.title == title


@pytest.mark.parametrize(
    ("location", "step_id", "suggested_values"),
    [
        pytest.param(
            config_flow.TYPE_SPECIFY_COORDINATES,
            "coordinates",
            {CONF_LATITUDE: 12.3, CONF_LONGITUDE: 45.6},
            id="coordinates",
        ),
        pytest.param(
            config_flow.TYPE_SPECIFY_COUNTRY,
            "country",
            {CONF_COUNTRY_CODE: None},
            id="country",
        ),
    ],
)
@pytest.mark.usefixtures("electricity_maps")
async def test_reconfigure_suggested_values(
    hass: HomeAssistant,
    location: str,
    step_id: str,
    suggested_values: dict[str, Any],
) -> None:
    """Test the reconfigure forms are prefilled with the current entry data."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "api_key", CONF_LATITUDE: 12.3, CONF_LONGITUDE: 45.6},
    )
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    assert _suggested_values(result) == {
        "location": config_flow.TYPE_SPECIFY_COORDINATES,
        CONF_API_KEY: "api_key",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"location": location, CONF_API_KEY: "api_key"},
    )
    assert result["step_id"] == step_id
    assert _suggested_values(result) == suggested_values


@pytest.mark.parametrize(
    ("side_effect", "err_code"),
    [
        pytest.param(
            ElectricityMapsInvalidTokenError, "invalid_auth", id="invalid_auth"
        ),
        pytest.param(ElectricityMapsNoDataError("No data"), "no_data", id="no_data"),
        pytest.param(ElectricityMapsError("Boom"), "unknown", id="unknown"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    electricity_maps: AsyncMock,
    side_effect: Exception,
    err_code: str,
) -> None:
    """Test reconfigure errors and recovery."""
    config_entry.add_to_hass(hass)
    electricity_maps.carbon_intensity_for_home_assistant.side_effect = side_effect

    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"location": config_flow.TYPE_USE_HOME, CONF_API_KEY: "api_key2"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": err_code}

    electricity_maps.carbon_intensity_for_home_assistant.side_effect = None

    with patch(
        "homeassistant.components.co2signal.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"location": config_flow.TYPE_USE_HOME, CONF_API_KEY: "api_key2"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {CONF_API_KEY: "api_key2"}
    assert config_entry.title == "Electricity Maps"
