"""Test DayBetter light local config flow."""

from errno import EADDRINUSE
from unittest.mock import AsyncMock, patch

from daybetter_local_api import DayBetterDevice

from homeassistant import config_entries
from homeassistant.components.daybetter_light_local.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEFAULT_CAPABILITIES


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


@patch(
    "homeassistant.components.daybetter_light_local.config_flow.DISCOVERY_TIMEOUT", 0
)
async def test_creating_entry_has_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_DayBetter_api: AsyncMock
) -> None:
    """Test setting up DayBetter with no devices."""

    mock_DayBetter_api.devices = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # 应该显示表单让用户手动输入
    assert result["type"] is FlowResultType.FORM

    # 提交表单后应该创建条目
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()


async def test_creating_entry_has_with_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_DayBetter_api: AsyncMock,
) -> None:
    """Test setting up DayBetter with devices."""

    mock_DayBetter_api.devices = _get_devices(mock_DayBetter_api)

    # 需要正确模拟发现过程和协调器
    with (
        patch(
            "homeassistant.components.daybetter_light_local.config_flow.DayBetterController",
            return_value=mock_DayBetter_api,
        ),
        patch(
            "homeassistant.components.daybetter_light_local.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.daybetter_light_local.coordinator.DayBetterLocalApiCoordinator.devices",
            new_callable=lambda: _get_devices(mock_DayBetter_api),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # 应该显示表单
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.168.1.100"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()

        # 现在应该被调用一次
        assert mock_DayBetter_api.start.call_count == 1
        mock_setup_entry.assert_awaited_once()


async def test_creating_entry_errno(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_DayBetter_api: AsyncMock,
) -> None:
    """Test setting up DayBetter with address in use error."""

    # 创建 OSError 并设置 errno
    e = OSError()
    e.errno = EADDRINUSE
    mock_DayBetter_api.start.side_effect = e

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # 确认表单
    assert result["type"] is FlowResultType.FORM

    # 配置时应该显示错误
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "address_in_use"

    await hass.async_block_till_done()
    mock_setup_entry.assert_not_awaited()
