"""Tests for the Datadog config flow."""

from unittest.mock import patch

from homeassistant.components import datadog
from homeassistant.components.datadog.config_flow import DatadogConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import MOCK_CONFIG

from tests.common import MockConfigEntry


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test user-initiated config flow."""
    with patch(
        "homeassistant.components.datadog.config_flow.validate_datadog_connection",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            datadog.DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == {}
        assert result2["options"] == MOCK_CONFIG


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection failure."""
    with patch(
        "homeassistant.components.datadog.config_flow.validate_datadog_connection",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            datadog.DOMAIN, context={"source": "user"}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.datadog.config_flow.validate_datadog_connection",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

        assert result3["type"] == FlowResultType.CREATE_ENTRY
        assert result3["data"] == {}
        assert result3["options"] == MOCK_CONFIG


async def test_import_flow(hass: HomeAssistant) -> None:
    """Test import triggers config flow and is accepted."""
    with patch(
        "homeassistant.components.datadog.config_flow.validate_datadog_connection",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            datadog.DOMAIN,
            context={"source": "import"},
            data=MOCK_CONFIG,
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == {}
        assert result["options"] == MOCK_CONFIG


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test updating options after setup."""
    mock_entry = MockConfigEntry(
        domain=datadog.DOMAIN,
        data={},
        options=MOCK_CONFIG,
        unique_id="datadog_unique",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    new_config = {
        "host": "127.0.0.1",
        "port": 8126,
        "prefix": "updated",
        "rate": 5,
    }

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=new_config
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {**MOCK_CONFIG, **new_config}


async def test_async_step_user_connection_fail(hass: HomeAssistant) -> None:
    """Test that the form shows an error when connection fails."""
    flow = DatadogConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.datadog.config_flow.validate_datadog_connection",
        return_value=False,
    ):
        result = await flow.async_step_user(
            {
                "host": "badhost",
                "port": 1234,
                "prefix": "prefix",
                "rate": 1,
            }
        )
        assert result["type"] == FlowResultType.FORM
        assert "cannot_connect" in result["errors"].get("base", "")
