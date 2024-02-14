"""Test the Hong Kong Observatory config flow."""

from unittest.mock import patch

from hko import HKOError

from homeassistant.components.hko.const import DEFAULT_LOCATION, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LOCATION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_config_flow_default(hass: HomeAssistant) -> None:
    """Test user config flow with default fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert "flow_id" in result

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: DEFAULT_LOCATION},
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == DEFAULT_LOCATION
    assert result2["result"].unique_id == DEFAULT_LOCATION
    assert result2["data"][CONF_LOCATION] == DEFAULT_LOCATION


async def test_config_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test user config flow without connection to the API."""
    with patch("homeassistant.components.hko.config_flow.HKO.weather") as client_mock:
        client_mock.side_effect = HKOError()
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_LOCATION: DEFAULT_LOCATION},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"

        client_mock.side_effect = None

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_LOCATION: DEFAULT_LOCATION},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == DEFAULT_LOCATION
        assert result["data"][CONF_LOCATION] == DEFAULT_LOCATION


async def test_config_flow_timeout(hass: HomeAssistant) -> None:
    """Test user config flow with timedout connection to the API."""
    with patch("homeassistant.components.hko.config_flow.HKO.weather") as client_mock:
        client_mock.side_effect = TimeoutError()
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_LOCATION: DEFAULT_LOCATION},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "unknown"

        client_mock.side_effect = None

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_LOCATION: DEFAULT_LOCATION},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == DEFAULT_LOCATION
        assert result["data"][CONF_LOCATION] == DEFAULT_LOCATION


async def test_config_flow_already_configured(hass: HomeAssistant) -> None:
    """Test user config flow with two equal entries."""
    r1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert r1["type"] == FlowResultType.FORM
    assert r1["step_id"] == SOURCE_USER
    assert "flow_id" in r1
    result1 = await hass.config_entries.flow.async_configure(
        r1["flow_id"],
        user_input={CONF_LOCATION: DEFAULT_LOCATION},
    )
    assert result1["type"] == FlowResultType.CREATE_ENTRY

    r2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert r2["type"] == FlowResultType.FORM
    assert r2["step_id"] == SOURCE_USER
    assert "flow_id" in r2
    result2 = await hass.config_entries.flow.async_configure(
        r2["flow_id"],
        user_input={CONF_LOCATION: DEFAULT_LOCATION},
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
