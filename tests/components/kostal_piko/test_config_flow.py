"""Test the Kostal Plenticore Solar Inverter config flow."""
import json
from unittest.mock import patch

import kostal

from homeassistant import data_entry_flow
from homeassistant.components.kostal_piko.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_BASE, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_show_empty(hass: HomeAssistant) -> None:
    """Test that the form is served empty."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"] == {}


async def test_integration_already_setup(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    with patch(
        "homeassistant.components.kostal_piko.Piko.fetch_props",
        return_value=kostal.DxsResponse.from_json(
            json.dumps(
                {
                    "session": {"sessionId": 0, "roleId": 0},
                    "status": {"code": 0},
                    "dxsEntries": [
                        {
                            "dxsId": kostal.SettingsGeneral.INVERTER_NAME,
                            "value": "my-inverter-name",
                        },
                        {
                            "dxsId": kostal.SettingsGeneral.INVERTER_MAKE,
                            "value": "my-inverter-make",
                        },
                        {
                            "dxsId": kostal.InfoVersions.SERIAL_NUMBER,
                            "value": "123456",
                        },
                    ],
                }
            )
        ),
    ):
        MockConfigEntry(
            domain=DOMAIN,
            unique_id="123456",
            data={
                CONF_HOST: "valid-host",
                CONF_USERNAME: "valid-user",
                CONF_PASSWORD: "valid-password",
            },
        ).add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: "valid-host",
                CONF_USERNAME: "valid-user",
                CONF_PASSWORD: "valid-password",
            },
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_invalid_host(hass):
    """Test connection failing with invalid host input."""
    with patch(
        "homeassistant.components.kostal_piko.Piko.fetch_props",
        side_effect=ConnectionError(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: "invalidhost",
                CONF_USERNAME: "valid-username",
                CONF_PASSWORD: "valid-password",
            },
        )

        assert result["errors"] == {CONF_HOST: "cannot_connect"}


async def test_none_host(hass):
    """Test connection failing with None host input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: None,
            CONF_USERNAME: "valid-username",
            CONF_PASSWORD: "valid-password",
        },
    )

    assert result["errors"] == {CONF_HOST: "not_specified"}


async def test_unknown_exception_thrown(hass):
    """Test what happens when an unknown exception is thrown."""
    with patch(
        "homeassistant.components.kostal_piko.Piko.fetch_props",
        side_effect=Exception("mocked unknown exception"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: "valid-host",
                CONF_USERNAME: "valid-username",
                CONF_PASSWORD: "valid-password",
            },
        )

        assert result["errors"] == {CONF_BASE: "unknown"}


async def test_valid_configuration(hass):
    """Test a valid configuration."""
    with patch(
        "homeassistant.components.kostal_piko.Piko.fetch_props",
        return_value=kostal.DxsResponse.from_json(
            json.dumps(
                {
                    "session": {"sessionId": 0, "roleId": 0},
                    "status": {"code": 0},
                    "dxsEntries": [
                        {
                            "dxsId": kostal.SettingsGeneral.INVERTER_NAME,
                            "value": "my-inverter-name",
                        },
                        {
                            "dxsId": kostal.SettingsGeneral.INVERTER_MAKE,
                            "value": "my-inverter-make",
                        },
                        {
                            "dxsId": kostal.InfoVersions.SERIAL_NUMBER,
                            "value": "123456",
                        },
                    ],
                }
            )
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: "valid-host",
                CONF_USERNAME: "valid-user",
                CONF_PASSWORD: "valid-password",
            },
        )

        assert "errors" not in result
        assert result["type"] == "create_entry"
        assert result["title"] == "my-inverter-make my-inverter-name (123456)"
        assert result["data"][CONF_HOST] == "valid-host"
        assert result["data"][CONF_USERNAME] == "valid-user"
        assert result["data"][CONF_PASSWORD] == "valid-password"
