"""Test aidot."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from homeassistant.components.aidot.__init__ import (
    async_setup_entry,
    async_unload_entry,
    cleanup_device_registry,
)
from homeassistant.components.aidot.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from tests.common import Mock

TEST_DEFAULT = {"device_list": [], "login_response": "", "product_list": []}


@pytest.fixture(name="aidot_init", autouse=True)
def aidot_init_fixture():
    """Aidot and entry setup."""
    with (
        patch(
            "homeassistant.components.aidot.__init__.Discover.broadcast_message",
            new=AsyncMock(),
        ),
    ):
        yield


async def test_async_setup_entry_calls_async_forward_entry_setups(
    hass: HomeAssistant,
) -> None:
    """Test that async_setup_entry calls async_forward_entry_setups correctly."""

    # 创建一个模拟的配置条目
    mock_entry = Mock(spec=ConfigEntry)
    mock_entry.domain = DOMAIN
    mock_entry.data = TEST_DEFAULT

    # 设置一个 mock 对象来接收属性赋值
    mock_data = {}
    hass.data = MagicMock()
    hass.data.setdefault = MagicMock(side_effect=mock_data.setdefault)
    with (
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ),
    ):
        await async_setup_entry(hass, mock_entry)
        hass.config_entries.async_forward_entry_setups.assert_called_once_with(
            mock_entry, ["light"]
        )


async def test_async_setup_entry_returns_true(hass: HomeAssistant) -> None:
    """Test that async_setup_entry returns True."""
    # 创建一个模拟的配置条目
    mock_entry = Mock(spec=ConfigEntry)
    mock_entry.domain = DOMAIN
    mock_entry.data = TEST_DEFAULT

    mock_data = {}
    hass.data = MagicMock()
    hass.data.setdefault = MagicMock(side_effect=mock_data.setdefault)
    with (
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ),
    ):
        result = await async_setup_entry(hass, mock_entry)
    assert result is True


async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Test that async_unload_entry unloads the component correctly."""

    # 创建一个模拟的配置条目
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.domain = DOMAIN
    mock_entry.data = TEST_DEFAULT

    # 初始化 hass.data 以包含一些示例数据
    mock_data = {}
    hass.data = MagicMock()
    hass.data.setdefault = MagicMock(side_effect=mock_data.setdefault)
    hass.data.setdefault(DOMAIN, {})["device_list"] = mock_entry.data["device_list"]
    hass.data.setdefault(DOMAIN, {})["login_response"] = mock_entry.data[
        "login_response"
    ]
    hass.data.setdefault(DOMAIN, {})["products"] = mock_entry.data["product_list"]

    # 确保 async_unload_platforms 是异步模拟
    with patch.object(
        hass.config_entries, "async_unload_platforms", new_callable=AsyncMock
    ) as mock_unload:
        await async_unload_entry(hass, mock_entry)
        mock_unload.assert_called_once_with(mock_entry, ["light"])
        assert DOMAIN not in hass.data


async def test_async_unload_entry_fails(hass: HomeAssistant) -> None:
    """Test that async_unload_entry handles failure correctly."""

    # 创建一个模拟的配置条目
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.domain = DOMAIN
    mock_entry.data = TEST_DEFAULT

    # 初始化 hass.data 以包含一些示例数据
    mock_data = {}
    hass.data = MagicMock()
    hass.data.setdefault = MagicMock(side_effect=mock_data.setdefault)
    hass.data.setdefault(DOMAIN, {})["device_list"] = mock_entry.data["device_list"]
    hass.data.setdefault(DOMAIN, {})["login_response"] = mock_entry.data[
        "login_response"
    ]
    hass.data.setdefault(DOMAIN, {})["products"] = mock_entry.data["product_list"]

    # 确保 async_unload_platforms 是异步模拟，并返回 False 表示卸载失败
    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new_callable=AsyncMock,
        return_value=False,
    ) as mock_unload:
        result = await async_unload_entry(hass, mock_entry)
        mock_unload.assert_called_once_with(mock_entry, ["light"])
        assert result is False
        assert hass.data.get(DOMAIN) is not None


async def test_cleanup_device_registry(hass: HomeAssistant) -> None:
    """Test that cleanup_device_registry removes devices correctly."""

    # 创建一个模拟的配置条目
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.entry_id = "test_entry_id"

    # 初始化设备注册表并添加一些示例设备
    device_registry = dr.async_get(hass)
    device_registry.devices = {
        "device_id_1": DeviceEntry(
            id="device_id_1",
            config_entries={"test_entry_id"},
            identifiers={("my_integration", "unique_id_1")},
        ),
        "device_id_2": DeviceEntry(
            id="device_id_2",
            config_entries={"other_entry_id"},
            identifiers={("my_integration", "unique_id_2")},
        ),
        "device_id_3": DeviceEntry(
            id="device_id_3",
            config_entries={"test_entry_id"},
            identifiers={("my_integration", "unique_id_3")},
        ),
    }

    # 模拟 device_registry.async_remove_device 方法
    with patch.object(
        device_registry, "async_remove_device", new_callable=AsyncMock
    ) as mock_remove:
        await cleanup_device_registry(hass)

        # 断言 async_remove_device 是否被调用并传入正确的参数
        expected_calls = [call("device_id_1"), call("device_id_2"), call("device_id_3")]
        mock_remove.assert_has_calls(expected_calls, any_order=True)
        assert mock_remove.call_count == 3  # 应该有两次调用


async def test_cleanup_device_registry_no_devices(hass: HomeAssistant) -> None:
    """Test that cleanup_device_registry handles the case where there are no devices to remove."""

    # 创建一个模拟的配置条目
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.entry_id = "test_entry_id"

    # 初始化设备注册表但不添加任何设备
    device_registry = dr.async_get(hass)
    device_registry.devices = {}

    # 模拟 device_registry.async_remove_device 方法
    with patch.object(
        device_registry, "async_remove_device", new_callable=AsyncMock
    ) as mock_remove:
        await cleanup_device_registry(hass)

        # 断言 async_remove_device 没有被调用
        mock_remove.assert_not_called()
