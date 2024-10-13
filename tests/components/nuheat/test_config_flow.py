"""Test the NuHeat config flow."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

import requests

from homeassistant import config_entries
from homeassistant.components.nuheat.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .mocks import _get_mock_thermostat_run


async def test_form_user(hass: HomeAssistant) -> None:
    """Test we get the form with user source."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_thermostat = _get_mock_thermostat_run()

    with (
        patch(
            "homeassistant.components.nuheat.config_flow.nuheat.NuHeat.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.nuheat.config_flow.nuheat.NuHeat.get_thermostat",
            return_value=mock_thermostat,
        ),
        patch(
            "homeassistant.components.nuheat.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL_NUMBER: "12345",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Master bathroom"
    assert result2["data"] == {
        CONF_SERIAL_NUMBER: "12345",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nuheat.config_flow.nuheat.NuHeat.authenticate",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL_NUMBER: "12345",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    response_mock = MagicMock()
    type(response_mock).status_code = 401
    with patch(
        "homeassistant.components.nuheat.config_flow.nuheat.NuHeat.authenticate",
        side_effect=requests.HTTPError(response=response_mock),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL_NUMBER: "12345",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_invalid_thermostat(hass: HomeAssistant) -> None:
    """Test we handle invalid thermostats."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    response_mock = MagicMock()
    type(response_mock).status_code = HTTPStatus.INTERNAL_SERVER_ERROR

    with (
        patch(
            "homeassistant.components.nuheat.config_flow.nuheat.NuHeat.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.nuheat.config_flow.nuheat.NuHeat.get_thermostat",
            side_effect=requests.HTTPError(response=response_mock),
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL_NUMBER: "12345",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_thermostat"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nuheat.config_flow.nuheat.NuHeat.authenticate",
        side_effect=requests.exceptions.Timeout,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL_NUMBER: "12345",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
