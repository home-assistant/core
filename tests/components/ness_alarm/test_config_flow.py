"""Test the Ness Alarm config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from nessclient import Client
import pytest

from homeassistant import config_entries
from homeassistant.components.ness_alarm.const import (
    CONF_INFER_ARMING_STATE,
    CONF_MAX_SUPPORTED_ZONES,
    CONF_SUPPORT_HOME_ARM,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_panel_info():
    """Mock panel info response."""
    panel_info = MagicMock()
    panel_info.model.value = "DPLUS8"
    panel_info.version = "12.1"
    return panel_info


async def test_form(hass: HomeAssistant, mock_panel_info) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.ness_alarm.config_flow.Client"
        ) as mock_client_class,
        patch(
            "homeassistant.components.ness_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_client = AsyncMock(spec=Client)
        mock_client_class.return_value = mock_client
        mock_client.get_panel_info = AsyncMock(return_value=mock_panel_info)
        mock_client.keepalive = AsyncMock()
        mock_client.close = AsyncMock()

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 2401,
                CONF_MAX_SUPPORTED_ZONES: 16,
                CONF_SCAN_INTERVAL: 60,
                CONF_INFER_ARMING_STATE: False,
                CONF_SUPPORT_HOME_ARM: True,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Ness Alarm DPLUS8 (192.168.1.100)"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 2401,
        CONF_MAX_SUPPORTED_ZONES: 16,
        CONF_SCAN_INTERVAL: 60,
        CONF_INFER_ARMING_STATE: False,
        CONF_SUPPORT_HOME_ARM: True,
    }


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ness_alarm.config_flow.Client"
    ) as mock_client_class:
        mock_client = AsyncMock(spec=Client)
        mock_client_class.return_value = mock_client
        mock_client.get_panel_info = AsyncMock(side_effect=TimeoutError())
        mock_client.keepalive = AsyncMock()
        mock_client.close = AsyncMock()

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 2401,
                CONF_MAX_SUPPORTED_ZONES: 16,
                CONF_SCAN_INTERVAL: 60,
                CONF_INFER_ARMING_STATE: False,
                CONF_SUPPORT_HOME_ARM: True,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_import(hass: HomeAssistant, mock_panel_info) -> None:
    """Test import from YAML."""
    with (
        patch(
            "homeassistant.components.ness_alarm.config_flow.Client"
        ) as mock_client_class,
        patch(
            "homeassistant.components.ness_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_client = AsyncMock(spec=Client)
        mock_client_class.return_value = mock_client
        mock_client.get_panel_info = AsyncMock(return_value=mock_panel_info)
        mock_client.keepalive = AsyncMock()
        mock_client.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 2401,
                CONF_INFER_ARMING_STATE: True,
                CONF_SUPPORT_HOME_ARM: False,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ness Alarm DPLUS8 (192.168.1.100)"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test config options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
            CONF_MAX_SUPPORTED_ZONES: 16,
            CONF_SCAN_INTERVAL: 60,
            CONF_INFER_ARMING_STATE: False,
            CONF_SUPPORT_HOME_ARM: True,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL: 120,
            CONF_INFER_ARMING_STATE: True,
            CONF_SUPPORT_HOME_ARM: False,
            CONF_MAX_SUPPORTED_ZONES: 8,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_SCAN_INTERVAL: 120,
        CONF_INFER_ARMING_STATE: True,
        CONF_SUPPORT_HOME_ARM: False,
        CONF_MAX_SUPPORTED_ZONES: 8,
    }
