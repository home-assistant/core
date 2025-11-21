"""Tests for Shelly services."""

from unittest.mock import AsyncMock, Mock

from aioshelly.exceptions import DeviceConnectionError, RpcCallError
import pytest

from homeassistant.components.shelly.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import init_integration


async def test_service_get_kvs_value(
    hass: HomeAssistant, mock_rpc_device: Mock, device_registry: dr.DeviceRegistry
) -> None:
    """Test get_kvs_value service."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    mock_rpc_device.call_rpc = AsyncMock(return_value={"value": "test_value"})

    response = await hass.services.async_call(
        DOMAIN,
        "get_kvs_value",
        {"device_id": device.id, "key": "my_key"},
        blocking=True,
        return_response=True,
    )

    assert response == {"value": "test_value"}
    mock_rpc_device.call_rpc.assert_called_once_with("KVS.Get", {"key": "my_key"})


async def test_service_get_kvs_value_invalid_device(hass: HomeAssistant) -> None:
    """Test get_kvs_value service with invalid device ID."""
    await init_integration(hass, 2)

    with pytest.raises(ServiceValidationError, match="Invalid device ID"):
        await hass.services.async_call(
            DOMAIN,
            "get_kvs_value",
            {"device_id": "invalid_device_id", "key": "my_key"},
            blocking=True,
            return_response=True,
        )


async def test_service_get_kvs_value_block_device(
    hass: HomeAssistant, mock_block_device: Mock, device_registry: dr.DeviceRegistry
) -> None:
    """Test get_kvs_value service with non-RPC (Gen1) device."""
    entry = await init_integration(hass, 1)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    with pytest.raises(ServiceValidationError, match="does not support KVS"):
        await hass.services.async_call(
            DOMAIN,
            "get_kvs_value",
            {"device_id": device.id, "key": "my_key"},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (RpcCallError(999), "RPC call error"),
        (DeviceConnectionError, "Device communication error"),
    ],
)
async def test_service_get_kvs_value_exc(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
    exc: Exception,
    error: str,
) -> None:
    """Test get_kvs_value service with exception."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    mock_rpc_device.call_rpc = AsyncMock(side_effect=exc)

    with pytest.raises(HomeAssistantError, match=error):
        await hass.services.async_call(
            DOMAIN,
            "get_kvs_value",
            {"device_id": device.id, "key": "my_key"},
            blocking=True,
            return_response=True,
        )
