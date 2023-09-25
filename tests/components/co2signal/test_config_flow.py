"""Test the CO2 Signal config flow."""
from json import JSONDecodeError
from unittest.mock import Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.co2signal import DOMAIN, config_flow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import VALID_PAYLOAD


async def test_form_home(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "CO2Signal.get_latest",
        return_value=VALID_PAYLOAD,
    ), patch(
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

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "CO2 Signal"
    assert result2["data"] == {
        "api_key": "api_key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_coordinates(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "location": config_flow.TYPE_SPECIFY_COORDINATES,
            "api_key": "api_key",
        },
    )
    assert result2["type"] == FlowResultType.FORM

    with patch(
        "CO2Signal.get_latest",
        return_value=VALID_PAYLOAD,
    ), patch(
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

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "12.3, 45.6"
    assert result3["data"] == {
        "latitude": 12.3,
        "longitude": 45.6,
        "api_key": "api_key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_country(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "location": config_flow.TYPE_SPECIFY_COUNTRY,
            "api_key": "api_key",
        },
    )
    assert result2["type"] == FlowResultType.FORM

    with patch(
        "CO2Signal.get_latest",
        return_value=VALID_PAYLOAD,
    ), patch(
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

    assert result3["type"] == FlowResultType.CREATE_ENTRY
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
            ValueError("Invalid authentication credentials"),
            "invalid_auth",
        ),
        (
            ValueError("API rate limit exceeded."),
            "api_ratelimit",
        ),
        (ValueError("Something else"), "unknown"),
        (JSONDecodeError(msg="boom", doc="", pos=1), "unknown"),
        (Exception("Boom"), "unknown"),
        (Mock(return_value={"error": "boom"}), "unknown"),
        (Mock(return_value={"status": "error"}), "unknown"),
    ],
    ids=[
        "invalid auth",
        "rate limit exceeded",
        "unknown value error",
        "json decode error",
        "unknown error",
        "error in json dict",
        "status error",
    ],
)
async def test_form_error_handling(hass: HomeAssistant, side_effect, err_code) -> None:
    """Test we handle expected errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "CO2Signal.get_latest",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "location": config_flow.TYPE_USE_HOME,
                "api_key": "api_key",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": err_code}

    with patch(
        "CO2Signal.get_latest",
        return_value=VALID_PAYLOAD,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "location": config_flow.TYPE_USE_HOME,
                "api_key": "api_key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "CO2 Signal"
    assert result["data"] == {
        "api_key": "api_key",
    }
