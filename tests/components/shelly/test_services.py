"""Tests for Shelly services."""

from unittest.mock import AsyncMock, Mock

from aioshelly.exceptions import DeviceConnectionError, RpcCallError
import pytest

from homeassistant.components.shelly.const import DOMAIN
from homeassistant.components.shelly.services import ATTR_KEY, SERVICE_GET_KVS_VALUE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
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
        SERVICE_GET_KVS_VALUE,
        {ATTR_DEVICE_ID: device.id, ATTR_KEY: "my_key"},
        blocking=True,
        return_response=True,
    )

    assert response == {"value": "test_value"}
    mock_rpc_device.call_rpc.assert_called_once_with("KVS.Get", {ATTR_KEY: "my_key"})


async def test_service_get_kvs_value_invalid_device(hass: HomeAssistant) -> None:
    """Test get_kvs_value service with invalid device ID."""
    await init_integration(hass, 2)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_KVS_VALUE,
            {ATTR_DEVICE_ID: "invalid_device_id", ATTR_KEY: "my_key"},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_device_id"
    assert exc_info.value.translation_placeholders == {
        ATTR_DEVICE_ID: "invalid_device_id"
    }


async def test_service_get_kvs_value_block_device(
    hass: HomeAssistant, mock_block_device: Mock, device_registry: dr.DeviceRegistry
) -> None:
    """Test get_kvs_value service with non-RPC (Gen1) device."""
    entry = await init_integration(hass, 1)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_KVS_VALUE,
            {ATTR_DEVICE_ID: device.id, ATTR_KEY: "my_key"},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "not_rpc_device"
    assert exc_info.value.translation_placeholders == {"device": entry.title}


@pytest.mark.parametrize(
    ("exc", "translation_key"),
    [
        (RpcCallError(999), "rpc_call_error"),
        (DeviceConnectionError, "device_communication_error"),
    ],
)
async def test_service_get_kvs_value_exc(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
    exc: Exception,
    translation_key: str,
) -> None:
    """Test get_kvs_value service with exception."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    mock_rpc_device.call_rpc = AsyncMock(side_effect=exc)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_KVS_VALUE,
            {ATTR_DEVICE_ID: device.id, ATTR_KEY: "my_key"},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == {"device": entry.title}


async def test_config_entry_not_loaded(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_rpc_device: Mock,
) -> None:
    """Test config entry not loaded."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_KVS_VALUE,
            {ATTR_DEVICE_ID: device.id, ATTR_KEY: "my_key"},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "entry_not_loaded"
    assert exc_info.value.translation_placeholders == {"device": entry.title}
