"""Tests for the Ambee config flow."""

from unittest.mock import patch

from ambee import AmbeeError

from homeassistant.components.ambee.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    with patch(
        "homeassistant.components.ambee.config_flow.Ambee.air_quality"
    ) as mock_ambee, patch(
        "homeassistant.components.ambee.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: "Name",
                CONF_API_KEY: "example",
                CONF_LATITUDE: 52.42,
                CONF_LONGITUDE: 4.44,
            },
        )

    assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY
    assert result2.get("title") == "Name"
    assert result2.get("data") == {
        CONF_API_KEY: "example",
        CONF_LATITUDE: 52.42,
        CONF_LONGITUDE: 4.44,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_ambee.mock_calls) == 1


async def test_api_error(hass: HomeAssistant) -> None:
    """Test API error."""
    with patch(
        "homeassistant.components.ambee.Ambee.air_quality",
        side_effect=AmbeeError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_NAME: "Name",
                CONF_API_KEY: "example",
                CONF_LATITUDE: 52.42,
                CONF_LONGITUDE: 4.44,
            },
        )

        assert result.get("type") == RESULT_TYPE_FORM
        assert result.get("errors") == {"base": "cannot_connect"}
