"""Test the UPB Control config flow."""

from asyncio import TimeoutError
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from homeassistant import config_entries
from homeassistant.components.upb.const import DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def mocked_upb(sync_complete=True, config_ok=True):
    """Mock UPB lib."""

    def _upb_lib_connect(callback):
        callback()

    upb_mock = AsyncMock()
    type(upb_mock).network_id = PropertyMock(return_value="42")
    type(upb_mock).config_ok = PropertyMock(return_value=config_ok)
    type(upb_mock).disconnect = MagicMock()
    if sync_complete:
        upb_mock.async_connect.side_effect = _upb_lib_connect
    return patch(
        "homeassistant.components.upb.config_flow.upb_lib.UpbPim", return_value=upb_mock
    )


async def valid_tcp_flow(
    hass: HomeAssistant, sync_complete: bool = True, config_ok: bool = True
) -> ConfigFlowResult:
    """Get result dict that are standard for most tests."""

    with (
        mocked_upb(sync_complete, config_ok),
        patch("homeassistant.components.upb.async_setup_entry", return_value=True),
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        return await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {"protocol": "TCP", "address": "1.2.3.4", "file_path": "upb.upe"},
        )


async def test_full_upb_flow_with_serial_port(hass: HomeAssistant) -> None:
    """Test a full UPB config flow with serial port."""

    with (
        mocked_upb(),
        patch(
            "homeassistant.components.upb.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {
                "protocol": "Serial port",
                "address": "/dev/ttyS0:115200",
                "file_path": "upb.upe",
            },
        )
        await hass.async_block_till_done()

    assert flow["type"] is FlowResultType.FORM
    assert flow["errors"] == {}
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UPB"
    assert result["data"] == {
        "host": "serial:///dev/ttyS0:115200",
        "file_path": "upb.upe",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_tcp_upb(hass: HomeAssistant) -> None:
    """Test we can setup a serial upb."""
    result = await valid_tcp_flow(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"host": "tcp://1.2.3.4", "file_path": "upb.upe"}
    await hass.async_block_till_done()


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""

    with patch(
        "homeassistant.components.upb.config_flow.asyncio.timeout",
        side_effect=TimeoutError,
    ):
        result = await valid_tcp_flow(hass, sync_complete=False)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_missing_upb_file(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await valid_tcp_flow(hass, config_ok=False)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_upb_file"}


async def test_form_user_with_already_configured(hass: HomeAssistant) -> None:
    """Test we can setup a TCP upb."""
    _ = await valid_tcp_flow(hass)
    result2 = await valid_tcp_flow(hass)
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
    await hass.async_block_till_done()
