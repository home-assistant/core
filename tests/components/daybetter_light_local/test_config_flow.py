"""Test DayBetter light local config flow."""

import asyncio
from errno import EADDRINUSE
from unittest.mock import AsyncMock, MagicMock, patch

from daybetter_local_api import DayBetterDevice

from homeassistant import config_entries
from homeassistant.components.daybetter_light_local.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEFAULT_CAPABILITIES


def _get_devices(mock_DayBetter_api: AsyncMock) -> list[DayBetterDevice]:
    """Helper to create a mock DayBetter device."""
    return [
        DayBetterDevice(
            controller=mock_DayBetter_api,
            ip="192.168.1.100",
            fingerprint="hhhhhhhhhhhhhhhhhhhhhhhhhhh",
            sku="P076",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]


async def test_creating_entry_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_DayBetter_api: AsyncMock
) -> None:
    """Test setting up DayBetter when no devices are found at all."""

    # 模拟自动发现返回空
    with patch(
        "homeassistant.components.daybetter_light_local.config_flow._async_discover_devices",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # 应该跳到手动输入步骤
        assert "type" in result
        assert result["type"] is FlowResultType.FORM
        assert "step_id" in result
        assert result["step_id"] == "manual"

        # 手动输入也没有设备
        with patch(
            "homeassistant.components.daybetter_light_local.config_flow.DayBetterController",
            return_value=mock_DayBetter_api,
        ):
            mock_DayBetter_api.devices = []
            mock_DayBetter_api.start = AsyncMock()
            mock_DayBetter_api.cleanup = MagicMock(return_value=asyncio.Event())
            mock_DayBetter_api.cleanup.return_value.set()

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"host": "192.168.1.100"}
            )

            # 此时应该显示 no_devices_found 错误
            assert "type" in result
            assert result["type"] is FlowResultType.FORM
            assert "errors" in result
            assert result["errors"] is not None
            assert result["errors"]["base"] == "no_devices_found"


async def test_creating_entry_address_in_use(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_DayBetter_api: AsyncMock
) -> None:
    """Test setting up DayBetter with EADDRINUSE error."""

    # 创建 OSError 并设置 errno
    e = OSError()
    e.errno = EADDRINUSE

    with patch(
        "homeassistant.components.daybetter_light_local.config_flow.DayBetterController",
        return_value=mock_DayBetter_api,
    ):
        mock_DayBetter_api.start.side_effect = e

        # 启动配置流
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # 跳转到手动输入
        assert "type" in result
        assert result["type"] is FlowResultType.FORM
        assert "step_id" in result
        assert result["step_id"] == "manual"

        # 提交 host 时应该显示 address_in_use 错误
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.168.1.100"}
        )
        assert "type" in result
        assert result["type"] is FlowResultType.FORM
        assert "errors" in result
        assert result["errors"] is not None
        assert result["errors"]["base"] == "address_in_use"

        await hass.async_block_till_done()
        mock_setup_entry.assert_not_awaited()


async def test_creating_entry_with_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_DayBetter_api: AsyncMock
) -> None:
    """Test setting up DayBetter when devices are found."""

    with patch(
        "homeassistant.components.daybetter_light_local.config_flow._async_discover_devices",
        return_value=[
            {
                "fingerprint": "hhhhhhhhhhhhhhhhhhhhhhhhhhh",
                "ip": "192.168.1.100",
                "sku": "P076",
                "name": "DayBetter P076",
            }
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # 设备选择表单
        assert "type" in result
        assert result["type"] is FlowResultType.FORM
        assert "step_id" in result
        assert result["step_id"] == "user"

        # 选择设备
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "hhhhhhhhhhhhhhhhhhhhhhhhhhh"}
        )
        assert "type" in result
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert "data" in result
        assert result["data"]["host"] == "192.168.1.100"


async def test_manual_entry_with_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_DayBetter_api: AsyncMock
) -> None:
    """Test manual entry when devices are found."""

    with patch(
        "homeassistant.components.daybetter_light_local.config_flow._async_discover_devices",
        return_value=[
            {
                "fingerprint": "hhhhhhhhhhhhhhhhhhhhhhhhhhh",
                "ip": "192.168.1.100",
                "sku": "P076",
                "name": "DayBetter P076",
            }
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # 选择手动输入
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "manual"}
        )
        assert "type" in result
        assert result["type"] is FlowResultType.FORM
        assert "step_id" in result
        assert result["step_id"] == "manual"

        # 手动输入 host 并发现设备
        with patch(
            "homeassistant.components.daybetter_light_local.config_flow.DayBetterController",
            return_value=mock_DayBetter_api,
        ):
            mock_DayBetter_api.devices = _get_devices(mock_DayBetter_api)
            mock_DayBetter_api.start = AsyncMock()
            mock_DayBetter_api.cleanup = MagicMock(return_value=asyncio.Event())
            mock_DayBetter_api.cleanup.return_value.set()

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"host": "192.168.1.100"}
            )
            assert "type" in result
            assert result["type"] is FlowResultType.CREATE_ENTRY
            assert "data" in result
            assert result["data"]["host"] == "192.168.1.100"
