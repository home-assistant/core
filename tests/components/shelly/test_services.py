"""Tests for Shelly services."""

from unittest.mock import Mock

from aioshelly.exceptions import DeviceConnectionError, RpcCallError
import pytest

from homeassistant.components.shelly.const import ATTR_KEY, ATTR_VALUE, DOMAIN
from homeassistant.components.shelly.services import (
    SERVICE_GET_KVS_VALUE,
    SERVICE_SET_KVS_VALUE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import init_integration

from tests.common import MockConfigEntry


async def test_service_get_kvs_value(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test get_kvs_value service."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    mock_rpc_device.kvs_get.return_value = {
        "etag": "16mLia9TRt8lGhj9Zf5Dp6Hw==",
        "value": "test_value",
    }

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_KVS_VALUE,
        {ATTR_DEVICE_ID: device.id, ATTR_KEY: "test_key"},
        blocking=True,
        return_response=True,
    )

    assert response == {"value": "test_value"}
    mock_rpc_device.kvs_get.assert_called_once_with("test_key")


async def test_service_get_kvs_value_invalid_device(hass: HomeAssistant) -> None:
    """Test get_kvs_value service with invalid device ID."""
    await init_integration(hass, 2)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_KVS_VALUE,
            {ATTR_DEVICE_ID: "invalid_device_id", ATTR_KEY: "test_key"},
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
            {ATTR_DEVICE_ID: device.id, ATTR_KEY: "test_key"},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "kvs_not_supported"
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

    mock_rpc_device.kvs_get.side_effect = exc

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_KVS_VALUE,
            {ATTR_DEVICE_ID: device.id, ATTR_KEY: "test_key"},
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
            {ATTR_DEVICE_ID: device.id, ATTR_KEY: "test_key"},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "entry_not_loaded"
    assert exc_info.value.translation_placeholders == {"device": entry.title}


async def test_service_get_kvs_value_sleeping_device(
    hass: HomeAssistant, mock_rpc_device: Mock, device_registry: dr.DeviceRegistry
) -> None:
    """Test get_kvs_value service with RPC sleeping device."""
    entry = await init_integration(hass, 2, sleep_period=1000)

    # Make device online
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_KVS_VALUE,
            {ATTR_DEVICE_ID: device.id, ATTR_KEY: "test_key"},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "kvs_not_supported"
    assert exc_info.value.translation_placeholders == {"device": entry.title}


async def test_service_set_kvs_value(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test set_kvs_value service."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_KVS_VALUE,
        {ATTR_DEVICE_ID: device.id, ATTR_KEY: "test_key", ATTR_VALUE: "test_value"},
        blocking=True,
    )

    mock_rpc_device.kvs_set.assert_called_once_with("test_key", "test_value")


async def test_service_get_kvs_value_config_entry_not_found(
    hass: HomeAssistant, mock_rpc_device: Mock, device_registry: dr.DeviceRegistry
) -> None:
    """Test device with no config entries."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    # Remove all config entries from device
    device_registry.devices[device.id].config_entries.clear()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_KVS_VALUE,
            {ATTR_DEVICE_ID: device.id, ATTR_KEY: "test_key"},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "config_entry_not_found"
    assert exc_info.value.translation_placeholders == {"device_id": device.id}


async def test_service_get_kvs_value_device_not_initialized(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test get_kvs_value if runtime_data.rpc is None."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    monkeypatch.delattr(entry.runtime_data, "rpc")

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_KVS_VALUE,
            {ATTR_DEVICE_ID: device.id, ATTR_KEY: "test_key"},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "device_not_initialized"
    assert exc_info.value.translation_placeholders == {"device": entry.title}


async def test_service_get_kvs_value_wrong_domain(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test get_kvs_value when device has config entries from different domains."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    # Create a config entry with different domain and add it to the device
    other_entry = MockConfigEntry(
        domain="other_domain",
        data={},
    )
    other_entry.add_to_hass(hass)

    # Add the other domain's config entry to the device
    device_registry.async_update_device(
        device.id, add_config_entry_id=other_entry.entry_id
    )

    # Remove the original Shelly config entry
    device_registry.async_update_device(
        device.id, remove_config_entry_id=entry.entry_id
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_KVS_VALUE,
            {ATTR_DEVICE_ID: device.id, ATTR_KEY: "test_key"},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "config_entry_not_found"
    assert exc_info.value.translation_placeholders == {"device_id": device.id}
