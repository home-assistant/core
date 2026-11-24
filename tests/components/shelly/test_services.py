"""Tests for Shelly services."""

from typing import Any
from unittest.mock import Mock

from aiohttp import ClientResponseError
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser

from homeassistant.components.shelly.const import (
    DOMAIN,
    ShellyService,
    ShellyServiceArgument,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CommonServiceArgument
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import device_registry as dr

from . import init_integration, register_device


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
        ShellyService.GET_KVS_VALUE,
        {
            CommonServiceArgument.DEVICE_ID: device.id,
            ShellyServiceArgument.KEY: "test_key",
        },
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
            ShellyService.GET_KVS_VALUE,
            {
                CommonServiceArgument.DEVICE_ID: "invalid_device_id",
                ShellyServiceArgument.KEY: "test_key",
            },
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == HOMEASSISTANT_DOMAIN
    assert exc_info.value.translation_key == "service_device_not_found"
    assert exc_info.value.translation_placeholders == {"device_id": "invalid_device_id"}


async def test_service_get_kvs_value_block_device(
    hass: HomeAssistant, mock_block_device: Mock, device_registry: dr.DeviceRegistry
) -> None:
    """Test get_kvs_value service with non-RPC (Gen1) device."""
    entry = await init_integration(hass, 1)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            ShellyService.GET_KVS_VALUE,
            {
                CommonServiceArgument.DEVICE_ID: device.id,
                ShellyServiceArgument.KEY: "test_key",
            },
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
            ShellyService.GET_KVS_VALUE,
            {
                CommonServiceArgument.DEVICE_ID: device.id,
                ShellyServiceArgument.KEY: "test_key",
            },
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
            ShellyService.GET_KVS_VALUE,
            {
                CommonServiceArgument.DEVICE_ID: device.id,
                ShellyServiceArgument.KEY: "test_key",
            },
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == HOMEASSISTANT_DOMAIN
    assert exc_info.value.translation_key == "service_config_entry_not_loaded"
    assert exc_info.value.translation_placeholders == {
        "domain": DOMAIN,
        "entry_title": entry.title,
    }


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
            ShellyService.GET_KVS_VALUE,
            {
                CommonServiceArgument.DEVICE_ID: device.id,
                ShellyServiceArgument.KEY: "test_key",
            },
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
        ShellyService.SET_KVS_VALUE,
        {
            CommonServiceArgument.DEVICE_ID: device.id,
            ShellyServiceArgument.KEY: "test_key",
            ShellyServiceArgument.VALUE: "test_value",
        },
        blocking=True,
    )

    mock_rpc_device.kvs_set.assert_called_once_with("test_key", "test_value")


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
            ShellyService.GET_KVS_VALUE,
            {
                CommonServiceArgument.DEVICE_ID: device.id,
                ShellyServiceArgument.KEY: "test_key",
            },
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "device_not_initialized"
    assert exc_info.value.translation_placeholders == {"device": entry.title}


@pytest.mark.usefixtures("mock_rpc_device")
async def test_service_get_kvs_value_wrong_domain(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test get_kvs_value when the device belongs to a different domain."""
    await init_integration(hass, 2)

    other_entry = MockConfigEntry(
        domain="other_domain",
        data={},
    )
    other_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other_domain", "other_device")},
        name="Other device",
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            ShellyService.GET_KVS_VALUE,
            {
                CommonServiceArgument.DEVICE_ID: device.id,
                ShellyServiceArgument.KEY: "test_key",
            },
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == HOMEASSISTANT_DOMAIN
    assert exc_info.value.translation_key == "service_device_wrong_domain"
    assert exc_info.value.translation_placeholders == {
        "device_name": device.name,
        "domain": DOMAIN,
    }


@pytest.mark.parametrize(
    ("data", "return_value", "expected_params", "expected_response"),
    [
        pytest.param(
            {
                ShellyServiceArgument.COMMAND: "Switch.Set",
                ShellyServiceArgument.PARAMS: {"id": 0, "on": True},
            },
            {"was_on": False},
            {"id": 0, "on": True},
            {"was_on": False},
            id="with_params",
        ),
        pytest.param(
            {ShellyServiceArgument.COMMAND: "Shelly.Reboot"},
            None,
            None,
            {},
            id="no_params_null_response",
        ),
    ],
)
async def test_service_command_rpc(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
    data: dict[str, Any],
    return_value: dict[str, Any] | None,
    expected_params: dict[str, Any] | None,
    expected_response: dict[str, Any],
) -> None:
    """Test command service with an RPC device."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    mock_rpc_device.call_rpc.reset_mock()
    mock_rpc_device.call_rpc.return_value = return_value

    response = await hass.services.async_call(
        DOMAIN,
        ShellyService.COMMAND,
        {CommonServiceArgument.DEVICE_ID: device.id, **data},
        blocking=True,
        return_response=True,
    )

    assert response == expected_response
    mock_rpc_device.call_rpc.assert_called_once_with(
        data[ShellyServiceArgument.COMMAND], expected_params
    )


@pytest.mark.parametrize(
    ("data", "expected_path", "expected_params"),
    [
        pytest.param(
            {
                ShellyServiceArgument.COMMAND: "/relay/0",
                ShellyServiceArgument.PARAMS: {"turn": "on", "timer": 30},
            },
            "relay/0",
            {"turn": "on", "timer": 30},
            id="leading_slash",
        ),
        pytest.param(
            {
                ShellyServiceArgument.COMMAND: "settings",
                ShellyServiceArgument.PARAMS: {"led_status_disable": True},
            },
            "settings",
            {"led_status_disable": "true"},
            id="boolean_param",
        ),
        pytest.param(
            {ShellyServiceArgument.COMMAND: "status"},
            "status",
            None,
            id="no_params",
        ),
    ],
)
async def test_service_command_block(
    hass: HomeAssistant,
    mock_block_device: Mock,
    device_registry: dr.DeviceRegistry,
    data: dict[str, Any],
    expected_path: str,
    expected_params: dict[str, Any] | None,
) -> None:
    """Test command service with a block device."""
    entry = await init_integration(hass, 1)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    mock_block_device.http_request.reset_mock()
    mock_block_device.http_request.return_value = {"ison": True}

    response = await hass.services.async_call(
        DOMAIN,
        ShellyService.COMMAND,
        {CommonServiceArgument.DEVICE_ID: device.id, **data},
        blocking=True,
        return_response=True,
    )

    assert response == {"ison": True}
    mock_block_device.http_request.assert_called_once_with(
        "get", expected_path, expected_params
    )


async def test_service_command_no_response(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test command service without requesting a response."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    mock_rpc_device.call_rpc.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        ShellyService.COMMAND,
        {
            CommonServiceArgument.DEVICE_ID: device.id,
            ShellyServiceArgument.COMMAND: "Switch.Toggle",
            ShellyServiceArgument.PARAMS: {"id": 0},
        },
        blocking=True,
    )

    mock_rpc_device.call_rpc.assert_called_once_with("Switch.Toggle", {"id": 0})


@pytest.mark.parametrize(
    ("gen", "data", "expected_command"),
    [
        pytest.param(
            2,
            {ShellyServiceArgument.COMMAND: "Shelly.FactoryReset"},
            "Shelly.FactoryReset",
            id="rpc_factory_reset",
        ),
        pytest.param(
            2,
            {ShellyServiceArgument.COMMAND: "shelly.resetwificonfig"},
            "shelly.resetwificonfig",
            id="rpc_reset_wifi_lowercase",
        ),
        pytest.param(
            1,
            {
                ShellyServiceArgument.COMMAND: "/Settings/",
                ShellyServiceArgument.PARAMS: {"reset": 1},
            },
            "Settings",
            id="block_factory_reset",
        ),
        pytest.param(
            1,
            {
                ShellyServiceArgument.COMMAND: "./settings",
                ShellyServiceArgument.PARAMS: {"reset": 1},
            },
            "settings",
            id="block_factory_reset_dot_segment",
        ),
        pytest.param(
            1,
            {
                ShellyServiceArgument.COMMAND: "relay/../settings/.",
                ShellyServiceArgument.PARAMS: {"reset": 1},
            },
            "settings",
            id="block_factory_reset_parent_segment",
        ),
        pytest.param(
            1,
            {
                ShellyServiceArgument.COMMAND: "../settings",
                ShellyServiceArgument.PARAMS: {"reset": 1},
            },
            "settings",
            id="block_factory_reset_above_root",
        ),
    ],
)
async def test_service_command_not_allowed(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
    gen: int,
    data: dict[str, Any],
    expected_command: str,
) -> None:
    """Test command service with a blocked command."""
    entry = await init_integration(hass, gen)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    mock_rpc_device.call_rpc.reset_mock()
    mock_block_device.http_request.reset_mock()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            ShellyService.COMMAND,
            {CommonServiceArgument.DEVICE_ID: device.id, **data},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "command_not_allowed"
    assert exc_info.value.translation_placeholders == {
        "device": entry.title,
        "command": expected_command,
    }
    mock_rpc_device.call_rpc.assert_not_called()
    mock_block_device.http_request.assert_not_called()


async def test_service_command_block_invalid_params(
    hass: HomeAssistant,
    mock_block_device: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test command service with nested params for a block device."""
    entry = await init_integration(hass, 1)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    mock_block_device.http_request.reset_mock()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            ShellyService.COMMAND,
            {
                CommonServiceArgument.DEVICE_ID: device.id,
                ShellyServiceArgument.COMMAND: "settings",
                ShellyServiceArgument.PARAMS: {"config": {"auto_off": 10}},
            },
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "command_invalid_params"
    assert exc_info.value.translation_placeholders == {"device": entry.title}
    mock_block_device.http_request.assert_not_called()


@pytest.mark.parametrize("gen", [1, 2])
@pytest.mark.usefixtures("mock_block_device", "mock_rpc_device")
async def test_service_command_sleeping_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    gen: int,
) -> None:
    """Test command service with a sleeping device."""
    entry = await init_integration(hass, gen, sleep_period=1000)

    device = register_device(device_registry, entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            ShellyService.COMMAND,
            {
                CommonServiceArgument.DEVICE_ID: device.id,
                ShellyServiceArgument.COMMAND: "status",
            },
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "command_sleeping_device"
    assert exc_info.value.translation_placeholders == {"device": entry.title}


@pytest.mark.parametrize(("gen", "attr"), [(1, "block"), (2, "rpc")])
@pytest.mark.usefixtures("mock_block_device", "mock_rpc_device")
async def test_service_command_device_not_initialized(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
    gen: int,
    attr: str,
) -> None:
    """Test command service with a device that is not initialized."""
    entry = await init_integration(hass, gen)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    monkeypatch.setattr(entry.runtime_data, attr, None)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            ShellyService.COMMAND,
            {
                CommonServiceArgument.DEVICE_ID: device.id,
                ShellyServiceArgument.COMMAND: "status",
            },
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "device_not_initialized"
    assert exc_info.value.translation_placeholders == {"device": entry.title}


async def test_service_command_rpc_not_connected(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test command service with a disconnected RPC device."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    mock_rpc_device.call_rpc.reset_mock()
    monkeypatch.setattr(mock_rpc_device, "connected", False)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            ShellyService.COMMAND,
            {
                CommonServiceArgument.DEVICE_ID: device.id,
                ShellyServiceArgument.COMMAND: "Shelly.GetStatus",
            },
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "device_communication_error"
    assert exc_info.value.translation_placeholders == {"device": entry.title}
    mock_rpc_device.call_rpc.assert_not_called()


@pytest.mark.parametrize(
    ("exc", "translation_key", "extra_placeholders"),
    [
        pytest.param(
            RpcCallError(-103, "Invalid argument 'id'"),
            "command_rpc_error",
            {
                "command": "Switch.Set",
                "code": "-103",
                "message": "Invalid argument 'id'",
            },
            id="rpc_call_error",
        ),
        pytest.param(
            DeviceConnectionError,
            "device_communication_error",
            {},
            id="device_connection_error",
        ),
    ],
)
async def test_service_command_exc(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
    exc: Exception,
    translation_key: str,
    extra_placeholders: dict[str, str],
) -> None:
    """Test command service when the device call fails."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    mock_rpc_device.call_rpc.side_effect = exc

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            ShellyService.COMMAND,
            {
                CommonServiceArgument.DEVICE_ID: device.id,
                ShellyServiceArgument.COMMAND: "Switch.Set",
            },
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == {
        "device": entry.title,
        **extra_placeholders,
    }


@pytest.mark.parametrize(
    ("cause", "translation_key", "extra_placeholders"),
    [
        pytest.param(
            ClientResponseError(Mock(), (), status=404),
            "command_http_error",
            {"command": "relay/9", "status": "404"},
            id="http_status_error",
        ),
        pytest.param(
            TimeoutError(),
            "device_communication_error",
            {},
            id="device_connection_error",
        ),
    ],
)
async def test_service_command_block_exc(
    hass: HomeAssistant,
    mock_block_device: Mock,
    device_registry: dr.DeviceRegistry,
    cause: Exception,
    translation_key: str,
    extra_placeholders: dict[str, str],
) -> None:
    """Test command service when the block device call fails."""
    entry = await init_integration(hass, 1)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    exc = DeviceConnectionError(cause)
    exc.__cause__ = cause
    mock_block_device.http_request.side_effect = exc

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            ShellyService.COMMAND,
            {
                CommonServiceArgument.DEVICE_ID: device.id,
                ShellyServiceArgument.COMMAND: "relay/9",
            },
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == {
        "device": entry.title,
        **extra_placeholders,
    }


@pytest.mark.parametrize(("gen", "command"), [(1, "status"), (2, "Shelly.GetStatus")])
async def test_service_command_auth_error(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
    gen: int,
    command: str,
) -> None:
    """Test command service starts reauth on authentication error."""
    entry = await init_integration(hass, gen)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    mock_block_device.http_request.side_effect = InvalidAuthError
    mock_rpc_device.call_rpc.side_effect = InvalidAuthError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            ShellyService.COMMAND,
            {
                CommonServiceArgument.DEVICE_ID: device.id,
                ShellyServiceArgument.COMMAND: command,
            },
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "auth_error"
    assert exc_info.value.translation_placeholders == {"device": entry.title}

    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id


@pytest.mark.usefixtures("mock_rpc_device")
async def test_service_command_requires_admin(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_read_only_user: MockUser,
) -> None:
    """Test command service is rejected for a non-admin user."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            ShellyService.COMMAND,
            {
                CommonServiceArgument.DEVICE_ID: device.id,
                ShellyServiceArgument.COMMAND: "Shelly.GetStatus",
            },
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
