"""Test the bzutech config flow."""

from unittest.mock import patch

import pytest
from requests import ConnectTimeout

from homeassistant.components.bzutech import BzuTech
from homeassistant.components.bzutech.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import ENTRY_CONFIG


@pytest.fixture
def bzutech_config_flow(hass: HomeAssistant):
    """Mock the bzutechapi for easier config flow testing."""
    with (
        patch.object(BzuTech, "start", return_value=True),
        patch.object(BzuTech, "get_endpoint_on", return_values="EP101"),
        patch.object(BzuTech, "get_device_names", return_value=["9245", "7564"]),
        patch("homeassistant.components.bzutech.config_flow.BzuTech") as mock_bzu,
    ):
        instance = mock_bzu.return_value = BzuTech("test@email.com", "test-password")

        instance.get_endpoint_on.return_value = "EP101"

        yield mock_bzu


async def test_form(hass: HomeAssistant, bzutech) -> None:
    """Test config_flow standard execution."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_CONFIG
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "deviceselect"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"Chip ID": "9245"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "portselect"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"sensorport": "Port 1 EP101"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_EMAIL] == ENTRY_CONFIG[CONF_EMAIL]
    assert result["data"][CONF_PASSWORD] == ENTRY_CONFIG[CONF_PASSWORD]


async def test_form_unexpected_exception(
    hass: HomeAssistant, bzutech_config_flow
) -> None:
    """Test any unexpected exception while creating api object."""
    bzutech_config_flow.side_effect = ConnectTimeout()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_CONFIG
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"
