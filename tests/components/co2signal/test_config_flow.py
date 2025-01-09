"""Test the CO2 Signal config flow."""

from unittest.mock import AsyncMock, patch

from aioelectricitymaps import (
    ElectricityMapsConnectionError,
    ElectricityMapsError,
    ElectricityMapsInvalidTokenError,
    ElectricityMapsNoDataError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.co2signal import config_flow
from homeassistant.components.co2signal.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


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
        return_value=True,
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
        return_value=True,
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
        return_value=True,
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

    electricity_maps.latest_carbon_intensity_by_coordinates.side_effect = side_effect
    electricity_maps.latest_carbon_intensity_by_country_code.side_effect = side_effect

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
    electricity_maps.latest_carbon_intensity_by_coordinates.side_effect = None
    electricity_maps.latest_carbon_intensity_by_country_code.side_effect = None

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
        return_value=True,
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
