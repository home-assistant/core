"""Test the vitrea config flow."""

from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.vitrea.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}


async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test we handle invalid host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "",  # Invalid empty host
            CONF_PORT: 11502,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"host": "invalid_host"}


async def test_form_invalid_port(hass: HomeAssistant) -> None:
    """Test we handle invalid port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Test with port that will fail schema validation (outside valid range)
    with pytest.raises(vol.Invalid):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 70000,  # Above max valid port (65535)
            },
        )


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vitrea.config_flow.VitreaClient"
    ) as client_mock:
        client_mock.return_value.connect.side_effect = ConnectionError
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 11502,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unexpected_exception(hass: HomeAssistant) -> None:
    """Test we handle unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vitrea.config_flow.VitreaConfigFlow._async_test_connection",
        side_effect=Exception("Unexpected error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.136",
                CONF_PORT: 11502,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we abort if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100", CONF_PORT: 11502},
        unique_id="vitrea_192.168.1.100_11502",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vitrea.config_flow.VitreaConfigFlow._async_test_connection",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 11502,
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_success(hass: HomeAssistant) -> None:
    """Test successful configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.vitrea.config_flow.VitreaConfigFlow._async_test_connection",
            return_value=None,
        ),
        patch(
            "homeassistant.components.vitrea.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 11502,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Vitrea 192.168.1.100:11502"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 11502,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_success_custom_port(hass: HomeAssistant) -> None:
    """Test successful configuration with custom port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.vitrea.config_flow.VitreaConfigFlow._async_test_connection",
            return_value=None,
        ),
        patch(
            "homeassistant.components.vitrea.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "10.0.0.100",
                CONF_PORT: 12345,
            },
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Vitrea 10.0.0.100:12345"
    assert result2["data"] == {
        CONF_HOST: "10.0.0.100",
        CONF_PORT: 12345,
    }
