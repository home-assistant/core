"""Tests for the ADS config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pyads
import pytest

from homeassistant import config_entries
from homeassistant.components.ads.const import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_pyads_connection():
    """Mock pyads Connection."""
    with patch("homeassistant.components.ads.config_flow.pyads.Connection") as mock_conn:
        connection = MagicMock()
        connection.open = MagicMock()
        connection.close = MagicMock()
        connection.read_device_info = MagicMock(
            return_value=MagicMock(name="TestDevice", version="1.0.0")
        )
        mock_conn.return_value = connection
        yield mock_conn


async def test_form(hass: HomeAssistant, mock_pyads_connection) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE: "192.168.1.100.1.1",
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PORT: 48898,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "ADS 192.168.1.100.1.1"
    assert result2["data"] == {
        CONF_DEVICE: "192.168.1.100.1.1",
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PORT: 48898,
    }


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_pyads_connection
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_pyads_connection.return_value.open.side_effect = pyads.ADSError()

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE: "192.168.1.100.1.1",
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PORT: 48898,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_already_configured(
    hass: HomeAssistant, mock_pyads_connection
) -> None:
    """Test we handle already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE: "192.168.1.100.1.1",
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PORT: 48898,
        },
        unique_id="192.168.1.100.1.1",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE: "192.168.1.100.1.1",
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PORT: 48898,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_unknown_error(
    hass: HomeAssistant, mock_pyads_connection
) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_pyads_connection.return_value.open.side_effect = Exception()

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE: "192.168.1.100.1.1",
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PORT: 48898,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
