"""Tests for the Ambee config flow."""

from unittest.mock import patch

from ambee import AmbeeAuthenticationError, AmbeeError

from homeassistant.components.ambee.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
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

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "Name"
    assert result2.get("data") == {
        CONF_API_KEY: "example",
        CONF_LATITUDE: 52.42,
        CONF_LONGITUDE: 4.44,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_ambee.mock_calls) == 1


async def test_full_flow_with_authentication_error(hass: HomeAssistant) -> None:
    """Test the full user configuration flow with an authentication error.

    This tests tests a full config flow, with a case the user enters an invalid
    API token, but recover by entering the correct one.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    with patch(
        "homeassistant.components.ambee.config_flow.Ambee.air_quality",
        side_effect=AmbeeAuthenticationError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: "Name",
                CONF_API_KEY: "invalid",
                CONF_LATITUDE: 52.42,
                CONF_LONGITUDE: 4.44,
            },
        )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == SOURCE_USER
    assert result2.get("errors") == {"base": "invalid_api_key"}
    assert "flow_id" in result2

    with patch(
        "homeassistant.components.ambee.config_flow.Ambee.air_quality"
    ) as mock_ambee, patch(
        "homeassistant.components.ambee.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={
                CONF_NAME: "Name",
                CONF_API_KEY: "example",
                CONF_LATITUDE: 52.42,
                CONF_LONGITUDE: 4.44,
            },
        )

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Name"
    assert result3.get("data") == {
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

    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}


async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reauthentication configuration flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"
    assert "flow_id" in result

    with patch(
        "homeassistant.components.ambee.config_flow.Ambee.air_quality"
    ) as mock_ambee, patch(
        "homeassistant.components.ambee.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "other_key"},
        )
        await hass.async_block_till_done()

    assert result2.get("type") == FlowResultType.ABORT
    assert result2.get("reason") == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_API_KEY: "other_key",
        CONF_LATITUDE: 52.42,
        CONF_LONGITUDE: 4.44,
    }

    assert len(mock_ambee.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_with_authentication_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reauthentication configuration flow with an authentication error.

    This tests tests a reauth flow, with a case the user enters an invalid
    API token, but recover by entering the correct one.
    """
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"
    assert "flow_id" in result

    with patch(
        "homeassistant.components.ambee.config_flow.Ambee.air_quality",
        side_effect=AmbeeAuthenticationError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "invalid",
            },
        )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "reauth_confirm"
    assert result2.get("errors") == {"base": "invalid_api_key"}
    assert "flow_id" in result2

    with patch(
        "homeassistant.components.ambee.config_flow.Ambee.air_quality"
    ) as mock_ambee, patch(
        "homeassistant.components.ambee.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "other_key"},
        )
        await hass.async_block_till_done()

    assert result3.get("type") == FlowResultType.ABORT
    assert result3.get("reason") == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_API_KEY: "other_key",
        CONF_LATITUDE: 52.42,
        CONF_LONGITUDE: 4.44,
    }

    assert len(mock_ambee.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_api_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test API error during reauthentication."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert "flow_id" in result

    with patch(
        "homeassistant.components.ambee.config_flow.Ambee.air_quality",
        side_effect=AmbeeError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "invalid",
            },
        )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "reauth_confirm"
    assert result2.get("errors") == {"base": "cannot_connect"}
