"""Tests for the TechnoVE config flow."""

from unittest.mock import MagicMock

import pytest
from technove import TechnoVEConnectionError

from homeassistant.components.technove.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry", "mock_technove")
async def test_full_user_flow_implementation(hass: HomeAssistant) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.123"}
    )

    assert result.get("title") == "TechnoVE Station"
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == "192.168.1.123"
    assert "result" in result
    assert result["result"].unique_id == "AA:AA:AA:AA:AA:BB"


@pytest.mark.usefixtures("mock_technove")
async def test_user_device_exists_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_technove: MagicMock,
) -> None:
    """Test we abort the config flow if TechnoVE station is already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.123"},
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_connection_error(hass: HomeAssistant, mock_technove: MagicMock) -> None:
    """Test we show user form on TechnoVE connection error."""
    mock_technove.update.side_effect = TechnoVEConnectionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "example.com"},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_setup_entry", "mock_technove")
async def test_full_user_flow_with_error(
    hass: HomeAssistant, mock_technove: MagicMock
) -> None:
    """Test the full manual user flow from start to finish with some errors in the middle."""
    mock_technove.update.side_effect = TechnoVEConnectionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.123"}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}

    mock_technove.update.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.123"}
    )

    assert result.get("title") == "TechnoVE Station"
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == "192.168.1.123"
    assert "result" in result
    assert result["result"].unique_id == "AA:AA:AA:AA:AA:BB"
