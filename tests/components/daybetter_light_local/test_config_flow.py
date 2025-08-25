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

from tests.common import MockConfigEntry


def _get_devices(mock_DayBetter_api: AsyncMock) -> list[DayBetterDevice]:
    return [
        DayBetterDevice(
            controller=mock_DayBetter_api,
            ip="192.168.1.169",
            fingerprint="hhhhhhhhhhhhhhhhhhhhhhhhhhh",
            sku="P076",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]


async def test_creating_entry_has_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_DayBetter_api: AsyncMock
) -> None:
    """Test setting up DayBetter with no devices."""

    # 模拟没有发现设备
    with patch(
        "homeassistant.components.daybetter_light_local.config_flow._async_discover_devices",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # 应该重定向到手动输入步骤
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # 模拟手动输入时也没有发现设备
        with patch(
            "homeassistant.components.daybetter_light_local.config_flow.DayBetterController",
            return_value=mock_DayBetter_api,
        ):
            # 确保控制器没有设备
            mock_DayBetter_api.devices = []
            mock_DayBetter_api.start = AsyncMock()
            mock_DayBetter_api.cleanup = MagicMock(return_value=asyncio.Event())
            mock_DayBetter_api.cleanup.return_value.set()

            # 提交手动输入的表单
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"host": "192.168.1.100"}
            )

            # 由于没有设备，应该显示错误
            assert result["type"] is FlowResultType.FORM
            assert result["errors"]["base"] == "no_devices_found"


async def test_creating_entry_has_with_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_DayBetter_api: AsyncMock,
) -> None:
    """Test setting up DayBetter with devices."""

    # 模拟发现设备
    with patch(
        "homeassistant.components.daybetter_light_local.config_flow._async_discover_devices",
        return_value=[
            {
                "fingerprint": "hhhhhhhhhhhhhhhhhhhhhhhhhhh",
                "ip": "192.168.1.169",
                "sku": "P076",
                "name": "DayBetter P076",
            }
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # 应该显示设备选择表单
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # 选择第一个设备
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "0"}
        )

        # 应该创建条目
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["host"] == "192.168.1.169"

        # 现在应该设置条目
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=result["data"],
            title=result["title"],
        )
        entry.add_to_hass(hass)

        # 模拟协调器设置
        with patch(
            "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
            return_value=mock_DayBetter_api,
        ):
            mock_DayBetter_api.devices = _get_devices(mock_DayBetter_api)
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

            # 现在应该被调用多次
            assert mock_setup_entry.call_count >= 1


async def test_creating_entry_errno(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_DayBetter_api: AsyncMock,
) -> None:
    """Test setting up DayBetter with address in use error."""

    # 创建 OSError 并设置 errno
    e = OSError()
    e.errno = EADDRINUSE

    # 模拟发现设备但连接时出现错误
    with (
        patch(
            "homeassistant.components.daybetter_light_local.config_flow._async_discover_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_light_local.config_flow.DayBetterController",
            return_value=mock_DayBetter_api,
        ),
    ):
        mock_DayBetter_api.start.side_effect = e

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # 应该重定向到手动输入
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # 配置时应该显示错误
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.168.1.100"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "address_in_use"

        await hass.async_block_till_done()
        mock_setup_entry.assert_not_awaited()


async def test_manual_entry_with_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_DayBetter_api: AsyncMock,
) -> None:
    """Test manual entry when devices are found."""

    with patch(
        "homeassistant.components.daybetter_light_local.config_flow._async_discover_devices",
        return_value=[
            {
                "fingerprint": "hhhhhhhhhhhhhhhhhhhhhhhhhhh",
                "ip": "192.168.1.169",
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

        # 应该重定向到手动输入步骤
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # 模拟手动输入成功发现设备
        with patch(
            "homeassistant.components.daybetter_light_local.config_flow.DayBetterController",
            return_value=mock_DayBetter_api,
        ):
            mock_DayBetter_api.devices = _get_devices(mock_DayBetter_api)
            mock_DayBetter_api.start = AsyncMock()
            mock_DayBetter_api.cleanup = MagicMock(return_value=asyncio.Event())
            mock_DayBetter_api.cleanup.return_value.set()

            # 提交手动输入
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"host": "192.168.1.100"}
            )

            # 应该创建条目
            assert result["type"] is FlowResultType.CREATE_ENTRY
            assert result["data"]["host"] == "192.168.1.100"
