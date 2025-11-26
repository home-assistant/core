"""Tests for Shelly services."""

from unittest.mock import Mock

from aioshelly.exceptions import DeviceConnectionError, RpcCallError
import pytest

from homeassistant.components.shelly.const import DOMAIN
from homeassistant.components.shelly.services import (
    ATTR_KEY,
    ATTR_VALUE,
    SERVICE_GET_KVS_VALUE,
    SERVICE_SET_KVS_VALUE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import init_integration


@pytest.mark.parametrize(
    ("raw_value", "expected_value"),
    [
        ("test_value", "test_value"),
        (42, 42),
        ('{"a":1}', {"a": 1}),
        ('[{"a":1},{"b":2}]', [{"a": 1}, {"b": 2}]),
    ],
)
async def test_service_get_kvs_value(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
    raw_value,
    expected_value,
) -> None:
    """Test get_kvs_value service."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    mock_rpc_device.kvs_get.return_value = {
        "etag": "16mLia9TRt8lGhj9Zf5Dp6Hw==",
        "value": raw_value,
    }

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_KVS_VALUE,
        {ATTR_DEVICE_ID: device.id, ATTR_KEY: "test_key"},
        blocking=True,
        return_response=True,
    )

    assert response == {"value": expected_value}
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


@pytest.mark.parametrize(
    ("raw_value", "expected_value"),
    [
        ("test_value", "test_value"),
        (42, 42),
        ({"a": 1}, '{"a":1}'),
        ([{"a": 1}, {"b": 2}], '[{"a":1},{"b":2}]'),
    ],
)
async def test_service_set_kvs_value(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
    raw_value,
    expected_value,
) -> None:
    """Test set_kvs_value service."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_KVS_VALUE,
        {ATTR_DEVICE_ID: device.id, ATTR_KEY: "test_key", ATTR_VALUE: raw_value},
        blocking=True,
    )

    mock_rpc_device.kvs_set.assert_called_once_with("test_key", expected_value)
