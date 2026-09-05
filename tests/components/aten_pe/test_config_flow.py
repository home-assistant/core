"""Tests for the ATEN PE config flow."""

from unittest.mock import AsyncMock, patch

from atenpdu import AtenPEError

from homeassistant import config_entries
from homeassistant.components.aten_pe.const import CONF_COMMUNITY, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_flow_user_success(hass: HomeAssistant) -> None:
    """Test user step success path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.aten_pe.config_flow.create_aten_pe_device"
        ) as mock_class,
        patch(
            "homeassistant.components.aten_pe.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        mock_device = AsyncMock()
        mock_device.initialize = AsyncMock()
        mock_device.deviceMAC = AsyncMock(return_value="00:11:22:33:44:55")
        mock_class.return_value = mock_device

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: "161",
                CONF_COMMUNITY: "private",
                CONF_USERNAME: "administrator",
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "192.168.1.100"
        assert result["data"] == {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: "161",
            CONF_COMMUNITY: "private",
            CONF_USERNAME: "administrator",
            "auth_key": "",
            "priv_key": "",
        }
        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection failure error handling in flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.aten_pe.config_flow.create_aten_pe_device"
    ) as mock_class:
        mock_device = AsyncMock()
        mock_device.initialize.side_effect = AtenPEError("SNMP Timeout")
        mock_class.return_value = mock_device

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: "161",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {CONF_HOST: "cannot_connect"}


async def test_flow_abort_if_unique_id_configured(hass: HomeAssistant) -> None:
    """Test entry is not created if unique_id is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: "161",
        },
        unique_id="192.168.1.100:161",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: "161",
        },
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_import_success(hass: HomeAssistant) -> None:
    """Test importing legacy YAML configuration."""
    with (
        patch(
            "homeassistant.components.aten_pe.config_flow.create_aten_pe_device"
        ) as mock_class,
        patch(
            "homeassistant.components.aten_pe.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        mock_device = AsyncMock()
        mock_device.initialize = AsyncMock()
        mock_device.deviceMAC = AsyncMock(return_value="00:11:22:33:44:55")
        mock_class.return_value = mock_device

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: "161",
                CONF_COMMUNITY: "private",
                CONF_USERNAME: "administrator",
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "192.168.1.100"
        assert result["data"] == {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: "161",
            CONF_COMMUNITY: "private",
            CONF_USERNAME: "administrator",
        }
        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1
