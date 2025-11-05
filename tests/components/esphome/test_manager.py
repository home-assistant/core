"""Test ESPHome manager."""

import asyncio
import base64
import logging
from typing import Any
from unittest.mock import AsyncMock, Mock, call, patch

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    AreaInfo,
    DeviceInfo,
    EncryptionPlaintextAPIError,
    HomeassistantServiceCall,
    InvalidAuthAPIError,
    InvalidEncryptionKeyAPIError,
    LogLevel,
    RequiresEncryptionAPIError,
    SubDeviceInfo,
    UserService,
    UserServiceArg,
    UserServiceArgType,
    ZWaveProxyRequest,
    ZWaveProxyRequestType,
)
import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.esphome.const import (
    CONF_ALLOW_SERVICE_CALLS,
    CONF_BLUETOOTH_MAC_ADDRESS,
    CONF_DEVICE_NAME,
    CONF_NOISE_PSK,
    CONF_SUBSCRIBE_LOGS,
    DOMAIN,
    STABLE_BLE_URL_VERSION,
    STABLE_BLE_VERSION_STR,
)
from homeassistant.components.esphome.encryption_key_storage import (
    ENCRYPTION_KEY_STORAGE_KEY,
)
from homeassistant.components.esphome.manager import DEVICE_CONFLICT_ISSUE_FORMAT
from homeassistant.components.tag import DOMAIN as TAG_DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    EVENT_HOMEASSISTANT_CLOSE,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.setup import async_setup_component

from .conftest import MockESPHomeDeviceType, MockGenericDeviceEntryType

from tests.common import (
    MockConfigEntry,
    async_call_logger_set_level,
    async_capture_events,
    async_mock_service,
)


async def test_esphome_device_subscribe_logs(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test configuring a device to subscribe to logs."""
    assert await async_setup_component(hass, "logger", {"logger": {}})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "fe80::1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
        },
        options={CONF_SUBSCRIBE_LOGS: True},
    )
    entry.add_to_hass(hass)
    device = await mock_esphome_device(
        mock_client=mock_client,
        entry=entry,
        device_info={},
    )
    await hass.async_block_till_done()

    async with async_call_logger_set_level(
        "homeassistant.components.esphome", "DEBUG", hass=hass, caplog=caplog
    ):
        assert device.current_log_level == LogLevel.LOG_LEVEL_VERY_VERBOSE

        caplog.set_level(logging.DEBUG)
        device.mock_on_log_message(
            Mock(level=LogLevel.LOG_LEVEL_INFO, message=b"test_log_message")
        )
        await hass.async_block_till_done()
        assert "test_log_message" in caplog.text

        device.mock_on_log_message(
            Mock(level=LogLevel.LOG_LEVEL_ERROR, message=b"test_error_log_message")
        )
        await hass.async_block_till_done()
        assert "test_error_log_message" in caplog.text

        caplog.set_level(logging.ERROR)
        device.mock_on_log_message(
            Mock(level=LogLevel.LOG_LEVEL_DEBUG, message=b"test_debug_log_message")
        )
        await hass.async_block_till_done()
        assert "test_debug_log_message" not in caplog.text

        caplog.set_level(logging.DEBUG)
        device.mock_on_log_message(
            Mock(level=LogLevel.LOG_LEVEL_DEBUG, message=b"test_debug_log_message")
        )
        await hass.async_block_till_done()
        assert "test_debug_log_message" in caplog.text

    async with async_call_logger_set_level(
        "homeassistant.components.esphome", "WARNING", hass=hass, caplog=caplog
    ):
        assert device.current_log_level == LogLevel.LOG_LEVEL_WARN
    async with async_call_logger_set_level(
        "homeassistant.components.esphome", "ERROR", hass=hass, caplog=caplog
    ):
        assert device.current_log_level == LogLevel.LOG_LEVEL_ERROR
    async with async_call_logger_set_level(
        "homeassistant.components.esphome", "INFO", hass=hass, caplog=caplog
    ):
        assert device.current_log_level == LogLevel.LOG_LEVEL_CONFIG


async def test_esphome_device_service_calls_not_allowed(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a device with service calls not allowed."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"esphome_version": "2023.3.0"},
    )
    await hass.async_block_till_done()
    mock_esphome_test = async_mock_service(hass, "esphome", "test")
    device.mock_service_call(
        HomeassistantServiceCall(
            service="esphome.test",
            data={},
        )
    )
    await hass.async_block_till_done()
    assert len(mock_esphome_test) == 0
    issue = issue_registry.async_get_issue(
        "esphome", "service_calls_not_enabled-11:22:33:44:55:aa"
    )
    assert issue is not None
    assert (
        "If you trust this device and want to allow access "
        "for it to make Home Assistant service calls, you can "
        "enable this functionality in the options flow"
    ) in caplog.text


async def test_esphome_device_service_calls_allowed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a device with service calls are allowed."""
    await async_setup_component(hass, TAG_DOMAIN, {})
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ALLOW_SERVICE_CALLS: True}
    )
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"esphome_version": "2023.3.0"},
        entry=mock_config_entry,
    )
    await hass.async_block_till_done()
    mock_calls: list[ServiceCall] = []

    async def _mock_service(call: ServiceCall) -> None:
        mock_calls.append(call)

    hass.services.async_register(DOMAIN, "test", _mock_service)
    device.mock_service_call(
        HomeassistantServiceCall(
            service="esphome.test",
            data={"raw": "data"},
        )
    )
    await hass.async_block_till_done()
    issue = issue_registry.async_get_issue(
        "esphome", "service_calls_not_enabled-11:22:33:44:55:aa"
    )
    assert issue is None
    assert len(mock_calls) == 1
    service_call = mock_calls[0]
    assert service_call.domain == DOMAIN
    assert service_call.service == "test"
    assert service_call.data == {"raw": "data"}
    mock_calls.clear()
    device.mock_service_call(
        HomeassistantServiceCall(
            service="esphome.test",
            data_template={"raw": "{{invalid}}"},
        )
    )
    await hass.async_block_till_done()
    assert (
        "Template variable warning: 'invalid' is undefined when rendering '{{invalid}}'"
        in caplog.text
    )
    assert len(mock_calls) == 1
    service_call = mock_calls[0]
    assert service_call.domain == DOMAIN
    assert service_call.service == "test"
    assert service_call.data == {"raw": ""}
    mock_calls.clear()
    caplog.clear()

    device.mock_service_call(
        HomeassistantServiceCall(
            service="esphome.test",
            data_template={"raw": "{{-- invalid --}}"},
        )
    )
    await hass.async_block_till_done()
    assert "TemplateSyntaxError" in caplog.text
    assert "{{-- invalid --}}" in caplog.text
    assert len(mock_calls) == 0
    mock_calls.clear()
    caplog.clear()

    device.mock_service_call(
        HomeassistantServiceCall(
            service="esphome.test",
            data_template={"raw": "{{var}}"},
            variables={"var": "value"},
        )
    )
    await hass.async_block_till_done()
    assert len(mock_calls) == 1
    service_call = mock_calls[0]
    assert service_call.domain == DOMAIN
    assert service_call.service == "test"
    assert service_call.data == {"raw": "value"}
    mock_calls.clear()

    device.mock_service_call(
        HomeassistantServiceCall(
            service="esphome.test",
            data_template={"raw": "valid"},
        )
    )
    await hass.async_block_till_done()
    assert len(mock_calls) == 1
    service_call = mock_calls[0]
    assert service_call.domain == DOMAIN
    assert service_call.service == "test"
    assert service_call.data == {"raw": "valid"}
    mock_calls.clear()

    # Try firing events
    events = async_capture_events(hass, "esphome.test")
    device.mock_service_call(
        HomeassistantServiceCall(
            service="esphome.test",
            is_event=True,
            data={"raw": "event"},
        )
    )
    await hass.async_block_till_done()
    assert len(events) == 1
    event = events[0]
    assert event.data["raw"] == "event"
    assert event.event_type == "esphome.test"
    events.clear()
    caplog.clear()

    # Try scanning a tag
    events = async_capture_events(hass, "tag_scanned")
    device.mock_service_call(
        HomeassistantServiceCall(
            service="esphome.tag_scanned",
            is_event=True,
            data={"tag_id": "1234"},
        )
    )
    await hass.async_block_till_done()
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "tag_scanned"
    assert event.data["tag_id"] == "1234"
    events.clear()
    caplog.clear()

    # Try firing events for disallowed domain
    events = async_capture_events(hass, "wrong.test")
    device.mock_service_call(
        HomeassistantServiceCall(
            service="wrong.test",
            is_event=True,
            data={"raw": "event"},
        )
    )
    await hass.async_block_till_done()
    assert len(events) == 0
    assert "Can only generate events under esphome domain" in caplog.text
    events.clear()


async def test_esphome_device_service_call_with_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test service call with response expected."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ALLOW_SERVICE_CALLS: True}
    )
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"esphome_version": "2023.3.0"},
        entry=mock_config_entry,
    )
    await hass.async_block_till_done()

    # Register a service that returns a response
    async def _mock_service_with_response(call: ServiceCall) -> dict[str, Any]:
        return {"result": "success", "value": 42}

    hass.services.async_register(
        DOMAIN,
        "test_with_response",
        _mock_service_with_response,
        supports_response=True,
    )

    # Mock the send_homeassistant_action_response method
    mock_client.send_homeassistant_action_response = Mock()

    # Call service with response expected
    device.mock_service_call(
        HomeassistantServiceCall(
            service="esphome.test_with_response",
            data={"input": "test"},
            call_id=123,
            wants_response=True,
        )
    )
    await hass.async_block_till_done()

    # Verify response was sent back to ESPHome
    mock_client.send_homeassistant_action_response.assert_called_once()
    call_id, success, error_message, response_data = (
        mock_client.send_homeassistant_action_response.call_args[0]
    )
    assert call_id == 123
    assert success is True
    assert error_message == ""
    assert response_data == b'{"response":{"result":"success","value":42}}'


async def test_esphome_device_service_call_with_response_template(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test service call with response template."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ALLOW_SERVICE_CALLS: True}
    )
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"esphome_version": "2023.3.0"},
        entry=mock_config_entry,
    )
    await hass.async_block_till_done()

    # Register a service that returns a response
    async def _mock_service_with_response(call: ServiceCall) -> dict[str, Any]:
        return {"temperature": 23.5, "humidity": 65}

    hass.services.async_register(
        DOMAIN, "get_data", _mock_service_with_response, supports_response=True
    )

    # Mock the send_homeassistant_action_response method
    mock_client.send_homeassistant_action_response = Mock()

    # Call service with response template
    device.mock_service_call(
        HomeassistantServiceCall(
            service="esphome.get_data",
            data={},
            call_id=456,
            wants_response=True,
            response_template="{{ response.temperature }}",
        )
    )
    await hass.async_block_till_done()

    # Verify response was sent back with template applied
    mock_client.send_homeassistant_action_response.assert_called_once()
    call_id, success, error_message, response_data = (
        mock_client.send_homeassistant_action_response.call_args[0]
    )
    assert call_id == 456
    assert success is True
    assert error_message == ""
    assert response_data == b'{"response":23.5}'


async def test_esphome_device_service_call_with_response_template_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test service call with invalid response template."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ALLOW_SERVICE_CALLS: True}
    )
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"esphome_version": "2023.3.0"},
        entry=mock_config_entry,
    )
    await hass.async_block_till_done()

    # Register a service that returns a response
    async def _mock_service_with_response(call: ServiceCall) -> dict[str, Any]:
        return {"temperature": 23.5}

    hass.services.async_register(
        DOMAIN, "get_data", _mock_service_with_response, supports_response=True
    )

    # Mock the send_homeassistant_action_response method
    mock_client.send_homeassistant_action_response = Mock()

    # Call service with invalid response template
    device.mock_service_call(
        HomeassistantServiceCall(
            service="esphome.get_data",
            data={},
            call_id=789,
            wants_response=True,
            response_template="{{ response.invalid_field }}",
        )
    )
    await hass.async_block_till_done()

    # Verify error response was sent back
    mock_client.send_homeassistant_action_response.assert_called_once()
    call_id, success, error_message, response_data = (
        mock_client.send_homeassistant_action_response.call_args[0]
    )
    assert call_id == 789
    assert success is False
    assert "Error rendering response template" in error_message
    assert response_data == b""


async def test_esphome_device_service_call_with_notification(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test service call with notification (no response expected)."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ALLOW_SERVICE_CALLS: True}
    )
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"esphome_version": "2023.3.0"},
        entry=mock_config_entry,
    )
    await hass.async_block_till_done()

    # Register a service without response
    async def _mock_service(call: ServiceCall) -> None:
        pass

    hass.services.async_register(DOMAIN, "test_notify", _mock_service)

    # Mock the send_homeassistant_action_response method
    mock_client.send_homeassistant_action_response = Mock()

    # Call service with call_id but no wants_response
    device.mock_service_call(
        HomeassistantServiceCall(
            service="esphome.test_notify",
            data={"input": "test"},
            call_id=999,
            wants_response=False,
        )
    )
    await hass.async_block_till_done()

    # Verify success notification was sent back
    mock_client.send_homeassistant_action_response.assert_called_once()
    call_id, success, error_message, response_data = (
        mock_client.send_homeassistant_action_response.call_args[0]
    )
    assert call_id == 999
    assert success is True
    assert error_message == ""
    assert response_data == b""


async def test_esphome_device_service_call_with_service_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test service call when service does not exist."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ALLOW_SERVICE_CALLS: True}
    )
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"esphome_version": "2023.3.0"},
        entry=mock_config_entry,
    )
    await hass.async_block_till_done()

    # Mock the send_homeassistant_action_response method
    mock_client.send_homeassistant_action_response = Mock()

    # Call non-existent service with notification
    device.mock_service_call(
        HomeassistantServiceCall(
            service="esphome.nonexistent",
            data={},
            call_id=111,
            wants_response=False,
        )
    )
    await hass.async_block_till_done()

    # Verify error notification was sent back
    mock_client.send_homeassistant_action_response.assert_called_once()
    call_id, success, error_message, response_data = (
        mock_client.send_homeassistant_action_response.call_args[0]
    )
    assert call_id == 111
    assert success is False
    assert "not found" in error_message.lower()
    assert response_data == b""


async def test_esphome_device_service_call_with_validation_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test service call with validation error."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ALLOW_SERVICE_CALLS: True}
    )
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"esphome_version": "2023.3.0"},
        entry=mock_config_entry,
    )
    await hass.async_block_till_done()

    # Register a service that validates input
    async def _mock_service(call: ServiceCall) -> None:
        raise vol.Invalid("Invalid input provided")

    hass.services.async_register(DOMAIN, "validate_test", _mock_service)

    # Mock the send_homeassistant_action_response method
    mock_client.send_homeassistant_action_response = Mock()

    # Call service with invalid data
    device.mock_service_call(
        HomeassistantServiceCall(
            service="esphome.validate_test",
            data={"invalid": "data"},
            call_id=222,
            wants_response=False,
        )
    )
    await hass.async_block_till_done()

    # Verify error notification was sent back
    mock_client.send_homeassistant_action_response.assert_called_once()
    call_id, success, error_message, response_data = (
        mock_client.send_homeassistant_action_response.call_args[0]
    )
    assert call_id == 222
    assert success is False
    assert "Invalid input provided" in error_message
    assert response_data == b""


async def test_esphome_device_service_call_fire_and_forget(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test fire-and-forget service call (no call_id)."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ALLOW_SERVICE_CALLS: True}
    )
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"esphome_version": "2023.3.0"},
        entry=mock_config_entry,
    )
    await hass.async_block_till_done()

    mock_calls: list[ServiceCall] = []

    async def _mock_service(call: ServiceCall) -> None:
        mock_calls.append(call)

    hass.services.async_register(DOMAIN, "fire_forget", _mock_service)

    # Mock the send_homeassistant_action_response method
    mock_client.send_homeassistant_action_response = Mock()

    # Call service without call_id (fire-and-forget)
    device.mock_service_call(
        HomeassistantServiceCall(
            service="esphome.fire_forget",
            data={"test": "data"},
        )
    )
    await hass.async_block_till_done()

    # Verify service was called but no response was sent
    assert len(mock_calls) == 1
    assert mock_calls[0].data == {"test": "data"}
    mock_client.send_homeassistant_action_response.assert_not_called()


async def test_esphome_device_with_old_bluetooth(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a device with old bluetooth creates an issue."""
    await mock_esphome_device(
        mock_client=mock_client,
        device_info={"bluetooth_proxy_feature_flags": 1, "esphome_version": "2023.3.0"},
    )
    await hass.async_block_till_done()
    issue = issue_registry.async_get_issue(
        "esphome", "ble_firmware_outdated-11:22:33:44:55:AA"
    )
    assert (
        issue.learn_more_url
        == f"https://esphome.io/changelog/{STABLE_BLE_URL_VERSION}.html"
    )


async def test_esphome_device_with_password(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a device with legacy password creates an issue."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            CONF_PASSWORD: "has",
        },
    )
    entry.add_to_hass(hass)
    await mock_esphome_device(
        mock_client=mock_client,
        device_info={"bluetooth_proxy_feature_flags": 0, "esphome_version": "2023.3.0"},
        entry=entry,
    )
    await hass.async_block_till_done()
    assert (
        issue_registry.async_get_issue(
            # This issue uses the ESPHome mac address which
            # is always UPPER case
            "esphome",
            "api_password_deprecated-11:22:33:44:55:AA",
        )
        is not None
    )


async def test_esphome_device_with_current_bluetooth(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a device with recent bluetooth does not create an issue."""
    await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "bluetooth_proxy_feature_flags": 1,
            "esphome_version": STABLE_BLE_VERSION_STR,
        },
    )
    await hass.async_block_till_done()
    assert (
        # This issue uses the ESPHome device info mac address which
        # is always UPPER case
        issue_registry.async_get_issue(
            "esphome", "ble_firmware_outdated-11:22:33:44:55:AA"
        )
        is None
    )


@pytest.mark.usefixtures("mock_zeroconf")
async def test_unique_id_updated_to_mac(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test we update config entry unique ID to MAC address."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="mock-config-name",
    )
    entry.add_to_hass(hass)
    subscribe_done = hass.loop.create_future()

    def async_subscribe_home_assistant_states_and_services(*args, **kwargs) -> None:
        subscribe_done.set_result(None)

    mock_client.subscribe_home_assistant_states_and_services = (
        async_subscribe_home_assistant_states_and_services
    )
    device_info = DeviceInfo(mac_address="1122334455aa")
    mock_client.device_info = AsyncMock(return_value=device_info)
    mock_client.list_entities_services = AsyncMock(return_value=([], []))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device_info, [], [])
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async with asyncio.timeout(1):
        await subscribe_done

    assert entry.unique_id == "11:22:33:44:55:aa"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_add_missing_bluetooth_mac_address(
    hass: HomeAssistant, mock_client
) -> None:
    """Test bluetooth mac is added if its missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="mock-config-name",
    )
    entry.add_to_hass(hass)
    subscribe_done = hass.loop.create_future()

    def async_subscribe_home_assistant_states_and_services(*args, **kwargs) -> None:
        subscribe_done.set_result(None)

    mock_client.subscribe_home_assistant_states_and_services = (
        async_subscribe_home_assistant_states_and_services
    )
    device_info = DeviceInfo(
        mac_address="1122334455aa",
        bluetooth_mac_address="AA:BB:CC:DD:EE:FF",
    )
    mock_client.device_info = AsyncMock(return_value=device_info)
    mock_client.list_entities_services = AsyncMock(return_value=([], []))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device_info, [], [])
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async with asyncio.timeout(1):
        await subscribe_done

    assert entry.unique_id == "11:22:33:44:55:aa"
    assert entry.data.get(CONF_BLUETOOTH_MAC_ADDRESS) == "AA:BB:CC:DD:EE:FF"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_unique_id_not_updated_if_name_same_and_already_mac(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test we never update the entry unique ID event if the name is the same."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)
    disconnect_done = hass.loop.create_future()

    def async_disconnect(*args, **kwargs) -> None:
        disconnect_done.set_result(None)

    mock_client.disconnect = async_disconnect
    device_info = DeviceInfo(mac_address="1122334455ab", name="test")
    mock_client.device_info = AsyncMock(return_value=device_info)
    mock_client.list_entities_services = AsyncMock(return_value=([], []))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device_info, [], [])
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async with asyncio.timeout(1):
        await disconnect_done

    # Mac should never update
    assert entry.unique_id == "11:22:33:44:55:aa"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_unique_id_updated_if_name_unset_and_already_mac(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test we never update config entry unique ID even if the name is unset."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)
    disconnect_done = hass.loop.create_future()

    def async_disconnect(*args, **kwargs) -> None:
        disconnect_done.set_result(None)

    mock_client.disconnect = async_disconnect
    device_info = DeviceInfo(mac_address="1122334455ab", name="test")
    mock_client.device_info = AsyncMock(return_value=device_info)
    mock_client.list_entities_services = AsyncMock(return_value=([], []))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device_info, [], [])
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async with asyncio.timeout(1):
        await disconnect_done

    # Mac should never update
    assert entry.unique_id == "11:22:33:44:55:aa"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_unique_id_not_updated_if_name_different_and_already_mac(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test we do not update config entry unique ID if the name is different."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)
    disconnect_done = hass.loop.create_future()

    def async_disconnect(*args, **kwargs) -> None:
        disconnect_done.set_result(None)

    mock_client.disconnect = async_disconnect
    device_info = DeviceInfo(mac_address="1122334455ab", name="different")
    mock_client.device_info = AsyncMock(return_value=device_info)
    mock_client.list_entities_services = AsyncMock(return_value=([], []))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device_info, [], [])
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async with asyncio.timeout(1):
        await disconnect_done

    # Mac should not be updated because name is different
    assert entry.unique_id == "11:22:33:44:55:aa"
    # Name should not be updated either
    assert entry.data[CONF_DEVICE_NAME] == "test"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_name_updated_only_if_mac_matches(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test we update config entry name only if the mac matches."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "old",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)
    subscribe_done = hass.loop.create_future()

    def async_subscribe_home_assistant_states_and_services(*args, **kwargs) -> None:
        subscribe_done.set_result(None)

    mock_client.subscribe_home_assistant_states_and_services = (
        async_subscribe_home_assistant_states_and_services
    )
    device_info = DeviceInfo(mac_address="1122334455aa", name="new")
    mock_client.device_info = AsyncMock(return_value=device_info)
    mock_client.list_entities_services = AsyncMock(return_value=([], []))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device_info, [], [])
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async with asyncio.timeout(1):
        await subscribe_done

    assert entry.unique_id == "11:22:33:44:55:aa"
    assert entry.data[CONF_DEVICE_NAME] == "new"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_name_updated_only_if_mac_was_unset(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test we update config entry name if the old unique id was not a mac."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "old",
        },
        unique_id="notamac",
    )
    entry.add_to_hass(hass)
    subscribe_done = hass.loop.create_future()

    def async_subscribe_home_assistant_states_and_services(*args, **kwargs) -> None:
        subscribe_done.set_result(None)

    mock_client.subscribe_home_assistant_states_and_services = (
        async_subscribe_home_assistant_states_and_services
    )
    device_info = DeviceInfo(mac_address="1122334455aa", name="new")
    mock_client.device_info = AsyncMock(return_value=device_info)
    mock_client.list_entities_services = AsyncMock(return_value=([], []))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device_info, [], [])
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async with asyncio.timeout(1):
        await subscribe_done

    assert entry.unique_id == "11:22:33:44:55:aa"
    assert entry.data[CONF_DEVICE_NAME] == "new"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_connection_aborted_wrong_device(
    hass: HomeAssistant,
    mock_client: APIClient,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test we abort the connection if the unique id is a mac and neither name or mac match."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.43.183",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)
    disconnect_done = hass.loop.create_future()

    async def async_disconnect(*args, **kwargs) -> None:
        disconnect_done.set_result(None)

    mock_client.disconnect = async_disconnect
    device_info = DeviceInfo(mac_address="1122334455ab", name="different")
    mock_client.device_info = AsyncMock(return_value=device_info)
    mock_client.list_entities_services = AsyncMock(return_value=([], []))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device_info, [], [])
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async with asyncio.timeout(1):
        await disconnect_done

    assert (
        "Unexpected device found at 192.168.43.183; expected `test` "
        "with mac address `11:22:33:44:55:aa`, found `different` "
        "with mac address `11:22:33:44:55:ab`" in caplog.text
    )
    # If its a different name, it means their DHCP
    # reservations are missing and the device is not
    # actually the same device, and there is nothing
    # we can do to fix it so we only log a warning
    assert not issue_registry.async_get_issue(
        domain=DOMAIN, issue_id=DEVICE_CONFLICT_ISSUE_FORMAT.format(entry.entry_id)
    )

    assert "Error getting setting up connection for" not in caplog.text
    mock_client.disconnect = AsyncMock()
    caplog.clear()
    # Make sure discovery triggers a reconnect
    service_info = DhcpServiceInfo(
        ip="192.168.43.184",
        hostname="test",
        macaddress="1122334455aa",
    )
    device_info = DeviceInfo(mac_address="1122334455aa", name="test")
    new_info = AsyncMock(return_value=device_info)
    mock_client.device_info = new_info
    # Also need to update device_info_and_list_entities
    new_combined_info = AsyncMock(return_value=(device_info, [], []))
    mock_client.device_info_and_list_entities = new_combined_info
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_DHCP}, data=service_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_updates"
    assert result["description_placeholders"] == {
        "title": "Mock Title",
        "name": "test",
        "mac": "11:22:33:44:55:aa",
    }
    assert entry.data[CONF_HOST] == "192.168.43.184"
    await hass.async_block_till_done()
    # Check that either device_info or device_info_and_list_entities was called
    assert len(new_info.mock_calls) + len(new_combined_info.mock_calls) == 2
    assert "Unexpected device found at" not in caplog.text


@pytest.mark.usefixtures("mock_zeroconf")
async def test_connection_aborted_wrong_device_same_name(
    hass: HomeAssistant,
    mock_client: APIClient,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test we abort the connection if the unique id is a mac and the name matches."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.43.183",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)
    disconnect_done = hass.loop.create_future()

    async def async_disconnect(*args, **kwargs) -> None:
        disconnect_done.set_result(None)

    mock_client.disconnect = async_disconnect
    device_info = DeviceInfo(mac_address="1122334455ab", name="test")
    mock_client.device_info = AsyncMock(return_value=device_info)
    mock_client.list_entities_services = AsyncMock(return_value=([], []))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device_info, [], [])
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async with asyncio.timeout(1):
        await disconnect_done

    assert (
        "Unexpected device found at 192.168.43.183; expected `test` "
        "with mac address `11:22:33:44:55:aa`, found `test` "
        "with mac address `11:22:33:44:55:ab`" in caplog.text
    )
    # We should start a repair flow to help them fix the issue
    assert issue_registry.async_get_issue(
        domain=DOMAIN, issue_id=DEVICE_CONFLICT_ISSUE_FORMAT.format(entry.entry_id)
    )

    assert "Error getting setting up connection for" not in caplog.text
    mock_client.disconnect = AsyncMock()
    caplog.clear()
    # Make sure discovery triggers a reconnect
    service_info = DhcpServiceInfo(
        ip="192.168.43.184",
        hostname="test",
        macaddress="1122334455aa",
    )
    device_info = DeviceInfo(mac_address="1122334455aa", name="test")
    new_info = AsyncMock(return_value=device_info)
    mock_client.device_info = new_info
    # Also need to update device_info_and_list_entities
    new_combined_info = AsyncMock(return_value=(device_info, [], []))
    mock_client.device_info_and_list_entities = new_combined_info
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_DHCP}, data=service_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_updates"
    assert result["description_placeholders"] == {
        "title": "Mock Title",
        "name": "test",
        "mac": "11:22:33:44:55:aa",
    }
    assert entry.data[CONF_HOST] == "192.168.43.184"
    await hass.async_block_till_done()
    # Check that either device_info or device_info_and_list_entities was called
    assert len(new_info.mock_calls) + len(new_combined_info.mock_calls) == 2
    assert "Unexpected device found at" not in caplog.text


@pytest.mark.usefixtures("mock_zeroconf")
async def test_failure_during_connect(
    hass: HomeAssistant,
    mock_client: APIClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we disconnect when there is a failure during connection setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.43.183",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)
    disconnect_done = hass.loop.create_future()

    async def async_disconnect(*args, **kwargs) -> None:
        disconnect_done.set_result(None)

    mock_client.disconnect = async_disconnect
    mock_client.device_info = AsyncMock(side_effect=APIConnectionError("fail"))
    mock_client.list_entities_services = AsyncMock(
        side_effect=APIConnectionError("fail")
    )
    mock_client.device_info_and_list_entities = AsyncMock(
        side_effect=APIConnectionError("fail")
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async with asyncio.timeout(1):
        await disconnect_done

    assert "Error getting setting up connection for" in caplog.text


async def test_state_subscription(
    mock_client: APIClient,
    hass: HomeAssistant,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test ESPHome subscribes to state changes."""
    device = await mock_esphome_device(
        mock_client=mock_client,
    )
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.test", "on", {"bool": True, "float": 3.0})
    device.mock_home_assistant_state_subscription("binary_sensor.test", None)
    await hass.async_block_till_done()
    assert mock_client.send_home_assistant_state.mock_calls == [
        call("binary_sensor.test", None, "on")
    ]
    mock_client.send_home_assistant_state.reset_mock()
    hass.states.async_set("binary_sensor.test", "off", {"bool": True, "float": 3.0})
    await hass.async_block_till_done()
    assert mock_client.send_home_assistant_state.mock_calls == [
        call("binary_sensor.test", None, "off")
    ]
    mock_client.send_home_assistant_state.reset_mock()
    device.mock_home_assistant_state_subscription("binary_sensor.test", "bool")
    await hass.async_block_till_done()
    assert mock_client.send_home_assistant_state.mock_calls == [
        call("binary_sensor.test", "bool", "on")
    ]
    mock_client.send_home_assistant_state.reset_mock()
    hass.states.async_set("binary_sensor.test", "off", {"bool": False, "float": 3.0})
    await hass.async_block_till_done()
    assert mock_client.send_home_assistant_state.mock_calls == [
        call("binary_sensor.test", "bool", "off")
    ]
    mock_client.send_home_assistant_state.reset_mock()
    device.mock_home_assistant_state_subscription("binary_sensor.test", "float")
    await hass.async_block_till_done()
    assert mock_client.send_home_assistant_state.mock_calls == [
        call("binary_sensor.test", "float", "3.0")
    ]
    mock_client.send_home_assistant_state.reset_mock()
    hass.states.async_set("binary_sensor.test", "on", {"bool": True, "float": 4.0})
    await hass.async_block_till_done()
    assert mock_client.send_home_assistant_state.mock_calls == [
        call("binary_sensor.test", None, "on"),
        call("binary_sensor.test", "bool", "on"),
        call("binary_sensor.test", "float", "4.0"),
    ]
    mock_client.send_home_assistant_state.reset_mock()
    hass.states.async_set("binary_sensor.test", "on", {})
    await hass.async_block_till_done()
    assert mock_client.send_home_assistant_state.mock_calls == []
    hass.states.async_remove("binary_sensor.test")
    await hass.async_block_till_done()
    assert mock_client.send_home_assistant_state.mock_calls == []


async def test_state_request(
    mock_client: APIClient,
    hass: HomeAssistant,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test ESPHome requests state change."""
    device = await mock_esphome_device(
        mock_client=mock_client,
    )
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.test", "on", {"bool": True, "float": 3.0})
    device.mock_home_assistant_state_request("binary_sensor.test", None)
    await hass.async_block_till_done()
    assert mock_client.send_home_assistant_state.mock_calls == [
        call("binary_sensor.test", None, "on")
    ]
    mock_client.send_home_assistant_state.reset_mock()
    hass.states.async_set("binary_sensor.test", "off", {"bool": False, "float": 5.0})
    await hass.async_block_till_done()
    assert mock_client.send_home_assistant_state.mock_calls == []


async def test_debug_logging(
    mock_client: APIClient,
    hass: HomeAssistant,
    mock_generic_device_entry: MockGenericDeviceEntryType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test enabling and disabling debug logging."""
    assert await async_setup_component(hass, "logger", {"logger": {}})
    await mock_generic_device_entry(
        mock_client=mock_client,
    )
    async with async_call_logger_set_level(
        "homeassistant.components.esphome", "DEBUG", hass=hass, caplog=caplog
    ):
        mock_client.set_debug.assert_has_calls([call(True)])
        mock_client.reset_mock()

    async with async_call_logger_set_level(
        "homeassistant.components.esphome", "WARNING", hass=hass, caplog=caplog
    ):
        mock_client.set_debug.assert_has_calls([call(False)])


async def test_esphome_device_with_dash_in_name_user_services(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a device with user services and a dash in the name."""
    service1 = UserService(
        name="my_service",
        key=1,
        args=[
            UserServiceArg(name="arg1", type=UserServiceArgType.BOOL),
            UserServiceArg(name="arg2", type=UserServiceArgType.INT),
            UserServiceArg(name="arg3", type=UserServiceArgType.FLOAT),
            UserServiceArg(name="arg4", type=UserServiceArgType.STRING),
            UserServiceArg(name="arg5", type=UserServiceArgType.BOOL_ARRAY),
            UserServiceArg(name="arg6", type=UserServiceArgType.INT_ARRAY),
            UserServiceArg(name="arg7", type=UserServiceArgType.FLOAT_ARRAY),
            UserServiceArg(name="arg8", type=UserServiceArgType.STRING_ARRAY),
        ],
    )
    service2 = UserService(
        name="simple_service",
        key=2,
        args=[
            UserServiceArg(name="arg1", type=UserServiceArgType.BOOL),
        ],
    )
    device = await mock_esphome_device(
        mock_client=mock_client,
        user_service=[service1, service2],
        device_info={"name": "with-dash"},
    )
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "with_dash_my_service")
    assert hass.services.has_service(DOMAIN, "with_dash_simple_service")

    await hass.services.async_call(DOMAIN, "with_dash_simple_service", {"arg1": True})
    await hass.async_block_till_done()

    mock_client.execute_service.assert_has_calls(
        [
            call(
                UserService(
                    name="simple_service",
                    key=2,
                    args=[UserServiceArg(name="arg1", type=UserServiceArgType.BOOL)],
                ),
                {"arg1": True},
            )
        ]
    )
    mock_client.execute_service.reset_mock()

    # Verify the service can be removed
    mock_client.list_entities_services = AsyncMock(return_value=([], [service1]))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device.device_info, [], [service1])
    )
    await device.mock_disconnect(True)
    await hass.async_block_till_done()
    await device.mock_connect()
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "with_dash_my_service")
    assert not hass.services.has_service(DOMAIN, "with_dash_simple_service")


async def test_esphome_user_services_ignores_invalid_arg_types(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a device with user services and a dash in the name."""
    service1 = UserService(
        name="bad_service",
        key=1,
        args=[
            UserServiceArg(name="arg1", type="wrong"),
        ],
    )
    service2 = UserService(
        name="simple_service",
        key=2,
        args=[
            UserServiceArg(name="arg1", type=UserServiceArgType.BOOL),
        ],
    )
    device = await mock_esphome_device(
        mock_client=mock_client,
        user_service=[service1, service2],
        device_info={"name": "with-dash"},
    )
    await hass.async_block_till_done()
    assert not hass.services.has_service(DOMAIN, "with_dash_bad_service")
    assert hass.services.has_service(DOMAIN, "with_dash_simple_service")

    await hass.services.async_call(DOMAIN, "with_dash_simple_service", {"arg1": True})
    await hass.async_block_till_done()

    mock_client.execute_service.assert_has_calls(
        [
            call(
                UserService(
                    name="simple_service",
                    key=2,
                    args=[UserServiceArg(name="arg1", type=UserServiceArgType.BOOL)],
                ),
                {"arg1": True},
            )
        ]
    )
    mock_client.execute_service.reset_mock()

    # Verify the service can be removed
    mock_client.list_entities_services = AsyncMock(return_value=([], [service2]))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device.device_info, [], [service2])
    )
    await device.mock_disconnect(True)
    await hass.async_block_till_done()
    await device.mock_connect()
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "with_dash_simple_service")
    assert not hass.services.has_service(DOMAIN, "with_dash_bad_service")


async def test_esphome_user_service_fails(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test executing a user service fails due to disconnect."""
    service1 = UserService(
        name="simple_service",
        key=2,
        args=[
            UserServiceArg(name="arg1", type=UserServiceArgType.BOOL),
        ],
    )
    await mock_esphome_device(
        mock_client=mock_client,
        user_service=[service1],
        device_info={"name": "with-dash"},
    )
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "with_dash_simple_service")

    mock_client.execute_service = Mock(side_effect=APIConnectionError("fail"))
    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            DOMAIN, "with_dash_simple_service", {"arg1": True}, blocking=True
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "action_call_failed"
    assert exc.value.translation_placeholders == {
        "call_name": "simple_service",
        "device_name": "with-dash",
        "error": "fail",
    }
    assert (
        str(exc.value)
        == "Failed to execute the action call simple_service on with-dash: fail"
    )

    mock_client.execute_service.assert_has_calls(
        [
            call(
                UserService(
                    name="simple_service",
                    key=2,
                    args=[UserServiceArg(name="arg1", type=UserServiceArgType.BOOL)],
                ),
                {"arg1": True},
            )
        ]
    )


async def test_esphome_user_services_changes(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a device with user services that change arguments."""
    service1 = UserService(
        name="simple_service",
        key=2,
        args=[
            UserServiceArg(name="arg1", type=UserServiceArgType.BOOL),
        ],
    )
    device = await mock_esphome_device(
        mock_client=mock_client,
        user_service=[service1],
        device_info={"name": "with-dash"},
    )
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "with_dash_simple_service")

    await hass.services.async_call(DOMAIN, "with_dash_simple_service", {"arg1": True})
    await hass.async_block_till_done()

    mock_client.execute_service.assert_has_calls(
        [
            call(
                UserService(
                    name="simple_service",
                    key=2,
                    args=[UserServiceArg(name="arg1", type=UserServiceArgType.BOOL)],
                ),
                {"arg1": True},
            )
        ]
    )
    mock_client.execute_service.reset_mock()

    new_service1 = UserService(
        name="simple_service",
        key=2,
        args=[
            UserServiceArg(name="arg1", type=UserServiceArgType.FLOAT),
        ],
    )

    # Verify the service can be updated
    mock_client.list_entities_services = AsyncMock(return_value=([], [new_service1]))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device.device_info, [], [new_service1])
    )
    await device.mock_disconnect(True)
    await hass.async_block_till_done()
    await device.mock_connect()
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "with_dash_simple_service")

    await hass.services.async_call(DOMAIN, "with_dash_simple_service", {"arg1": 4.5})
    await hass.async_block_till_done()

    mock_client.execute_service.assert_has_calls(
        [
            call(
                UserService(
                    name="simple_service",
                    key=2,
                    args=[UserServiceArg(name="arg1", type=UserServiceArgType.FLOAT)],
                ),
                {"arg1": 4.5},
            )
        ]
    )
    mock_client.execute_service.reset_mock()


async def test_esphome_device_with_suggested_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a device with suggested area."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"suggested_area": "kitchen"},
    )
    await hass.async_block_till_done()
    entry = device.entry
    dev = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, entry.unique_id)}
    )
    assert dev.area_id == area_registry.async_get_area_by_name("kitchen").id


async def test_esphome_device_area_priority(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test that device_info.area takes priority over suggested_area."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "suggested_area": "kitchen",
            "area": AreaInfo(area_id=0, name="Living Room"),
        },
    )
    await hass.async_block_till_done()
    entry = device.entry
    dev = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, entry.unique_id)}
    )
    # Should use device_info.area.name instead of suggested_area
    assert dev.area_id == area_registry.async_get_area_by_name("Living Room").id


async def test_esphome_device_with_project(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a device with a project."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"project_name": "mfr.model", "project_version": "2.2.2"},
    )
    await hass.async_block_till_done()
    entry = device.entry
    dev = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, entry.unique_id)}
    )
    assert dev.manufacturer == "mfr"
    assert dev.model == "model"
    assert dev.sw_version == "2.2.2 (ESPHome 1.0.0)"


async def test_esphome_device_with_manufacturer(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a device with a manufacturer."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"manufacturer": "acme"},
    )
    await hass.async_block_till_done()
    entry = device.entry
    dev = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, entry.unique_id)}
    )
    assert dev.manufacturer == "acme"


async def test_esphome_device_with_web_server(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a device with a web server."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"webserver_port": 80},
    )
    await hass.async_block_till_done()
    entry = device.entry
    dev = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, entry.unique_id)}
    )
    assert dev.configuration_url == "http://test.local:80"


async def test_esphome_device_with_ipv6_web_server(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a device with a web server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "fe80::1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
        },
        options={},
    )
    entry.add_to_hass(hass)
    device = await mock_esphome_device(
        mock_client=mock_client,
        entry=entry,
        device_info={"webserver_port": 80},
    )
    await hass.async_block_till_done()
    entry = device.entry
    dev = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, entry.unique_id)}
    )
    assert dev.configuration_url == "http://[fe80::1]:80"


async def test_esphome_device_with_compilation_time(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a device with a compilation_time."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"compilation_time": "comp_time"},
    )
    await hass.async_block_till_done()
    entry = device.entry
    dev = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, entry.unique_id)}
    )
    assert "comp_time" in dev.sw_version


async def test_disconnects_at_close_event(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test the device is disconnected at the close event."""
    await mock_esphome_device(
        mock_client=mock_client,
        device_info={"compilation_time": "comp_time"},
    )
    await hass.async_block_till_done()

    assert mock_client.disconnect.call_count == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()
    assert mock_client.disconnect.call_count == 1


@pytest.mark.parametrize(
    "error",
    [
        EncryptionPlaintextAPIError,
        RequiresEncryptionAPIError,
        InvalidEncryptionKeyAPIError,
        InvalidAuthAPIError,
    ],
)
async def test_start_reauth(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    error: Exception,
) -> None:
    """Test exceptions on connect error trigger reauth."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"compilation_time": "comp_time"},
    )
    await hass.async_block_till_done()

    await device.mock_connect_error(error("fail"))
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress(DOMAIN)
    assert len(flows) == 1
    flow = flows[0]
    assert flow["context"]["source"] == "reauth"


async def test_no_reauth_wrong_mac(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test exceptions on connect error trigger reauth."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"compilation_time": "comp_time"},
    )
    await hass.async_block_till_done()

    await device.mock_connect_error(
        InvalidEncryptionKeyAPIError(
            "fail", received_mac="aabbccddeeff", received_name="test"
        )
    )
    await hass.async_block_till_done()

    # Reauth should not be triggered
    flows = hass.config_entries.flow.async_progress(DOMAIN)
    assert len(flows) == 0
    assert (
        "Unexpected device found at test.local; expected `test` "
        "with mac address `11:22:33:44:55:aa`, found `test` "
        "with mac address `aa:bb:cc:dd:ee:ff`" in caplog.text
    )


async def test_auth_error_during_on_connect_triggers_reauth(
    hass: HomeAssistant,
    mock_client: APIClient,
) -> None:
    """Test that InvalidAuthAPIError during on_connect triggers reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="11:22:33:44:55:aa",
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            CONF_PASSWORD: "wrong_password",
        },
    )
    entry.add_to_hass(hass)

    mock_client.device_info_and_list_entities = AsyncMock(
        side_effect=InvalidAuthAPIError("Invalid password!")
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"
    assert flows[0]["context"]["entry_id"] == entry.entry_id
    assert mock_client.disconnect.call_count >= 1


async def test_entry_missing_unique_id(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test the unique id is added from storage if available."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
        },
        options={CONF_ALLOW_SERVICE_CALLS: True},
    )
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, mock_storage=True)
    await hass.async_block_till_done()
    assert entry.unique_id == "11:22:33:44:55:aa"


async def test_entry_missing_bluetooth_mac_address(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test the bluetooth_mac_address is added if available."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
        },
        options={CONF_ALLOW_SERVICE_CALLS: True},
    )
    entry.add_to_hass(hass)
    await mock_esphome_device(
        mock_client=mock_client,
        mock_storage=True,
        device_info={"bluetooth_mac_address": "AA:BB:CC:DD:EE:FC"},
    )
    await hass.async_block_till_done()
    assert entry.data[CONF_BLUETOOTH_MAC_ADDRESS] == "AA:BB:CC:DD:EE:FC"


async def test_device_adds_friendly_name(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a device with user services that change arguments."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"name": "nofriendlyname", "friendly_name": ""},
    )
    await hass.async_block_till_done()
    dev_reg = dr.async_get(hass)
    dev = dev_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, device.entry.unique_id)}
    )
    assert dev.name == "Nofriendlyname"
    assert (
        "No `friendly_name` set in the `esphome:` section of "
        "the YAML config for device 'nofriendlyname'"
    ) in caplog.text
    caplog.clear()

    await device.mock_disconnect(True)
    await hass.async_block_till_done()
    device.device_info = DeviceInfo(
        **{**device.device_info.to_dict(), "friendly_name": "I have a friendly name"}
    )
    mock_client.device_info = AsyncMock(return_value=device.device_info)
    mock_client.list_entities_services = AsyncMock(return_value=([], []))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device.device_info, [], [])
    )
    await device.mock_connect()
    await hass.async_block_till_done()
    dev = dev_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, device.entry.unique_id)}
    )
    assert dev.name == "I have a friendly name"
    assert (
        "No `friendly_name` set in the `esphome:` section of the YAML config for device"
    ) not in caplog.text


async def test_assist_in_progress_issue_deleted(
    hass: HomeAssistant,
    mock_client: APIClient,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test assist in progress entity and issue is deleted.

    Remove this cleanup after 2026.4
    """
    entry = entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform="binary_sensor",
        unique_id="11:22:33:44:55:AA-assist_in_progress",
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"assist_in_progress_deprecated_{entry.id}",
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="assist_in_progress_deprecated",
        translation_placeholders={
            "integration_name": "ESPHome",
        },
    )
    await mock_esphome_device(
        mock_client=mock_client,
        device_info={},
        mock_storage=True,
    )
    assert (
        entity_registry.async_get_entity_id(
            DOMAIN, "binary_sensor", "11:22:33:44:55:AA-assist_in_progress"
        )
        is None
    )
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"assist_in_progress_deprecated_{entry.id}"
        )
        is None
    )


async def test_sub_device_creation(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test sub devices are created in device registry."""
    device_registry = dr.async_get(hass)

    # Define areas
    areas = [
        AreaInfo(area_id=1, name="Living Room"),
        AreaInfo(area_id=2, name="Bedroom"),
        AreaInfo(area_id=3, name="Kitchen"),
    ]

    # Define sub devices
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="Motion Sensor", area_id=1),
        SubDeviceInfo(device_id=22222222, name="Light Switch", area_id=1),
        SubDeviceInfo(device_id=33333333, name="Temperature Sensor", area_id=2),
    ]

    device_info = {
        "areas": areas,
        "devices": sub_devices,
        "area": AreaInfo(area_id=0, name="Main Hub"),
    }

    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
    )

    # Check main device is created
    main_device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, device.device_info.mac_address)}
    )
    assert main_device is not None
    assert main_device.area_id == area_registry.async_get_area_by_name("Main Hub").id

    # Check sub devices are created
    sub_device_1 = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{device.device_info.mac_address}_11111111")}
    )
    assert sub_device_1 is not None
    assert sub_device_1.name == "Motion Sensor"
    assert (
        sub_device_1.area_id == area_registry.async_get_area_by_name("Living Room").id
    )
    assert sub_device_1.via_device_id == main_device.id

    sub_device_2 = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{device.device_info.mac_address}_22222222")}
    )
    assert sub_device_2 is not None
    assert sub_device_2.name == "Light Switch"
    assert (
        sub_device_2.area_id == area_registry.async_get_area_by_name("Living Room").id
    )
    assert sub_device_2.via_device_id == main_device.id

    sub_device_3 = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{device.device_info.mac_address}_33333333")}
    )
    assert sub_device_3 is not None
    assert sub_device_3.name == "Temperature Sensor"
    assert sub_device_3.area_id == area_registry.async_get_area_by_name("Bedroom").id
    assert sub_device_3.via_device_id == main_device.id


async def test_sub_device_cleanup(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test sub devices are removed when they no longer exist."""
    device_registry = dr.async_get(hass)

    # Initial sub devices
    sub_devices_initial = [
        SubDeviceInfo(device_id=11111111, name="Device 1", area_id=0),
        SubDeviceInfo(device_id=22222222, name="Device 2", area_id=0),
        SubDeviceInfo(device_id=33333333, name="Device 3", area_id=0),
    ]

    device_info = {
        "devices": sub_devices_initial,
    }

    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
    )

    # Verify all sub devices exist
    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, f"{device.device_info.mac_address}_11111111")}
        )
        is not None
    )
    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, f"{device.device_info.mac_address}_22222222")}
        )
        is not None
    )
    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, f"{device.device_info.mac_address}_33333333")}
        )
        is not None
    )

    # Now update with fewer sub devices (device 2 removed)
    sub_devices_updated = [
        SubDeviceInfo(device_id=11111111, name="Device 1", area_id=0),
        SubDeviceInfo(device_id=33333333, name="Device 3", area_id=0),
    ]

    # Update device info
    device.device_info = DeviceInfo(
        name="test",
        friendly_name="Test",
        esphome_version="1.0.0",
        mac_address="11:22:33:44:55:AA",
        devices=sub_devices_updated,
    )

    # Update the mock client to return the new device info
    mock_client.device_info = AsyncMock(return_value=device.device_info)
    mock_client.list_entities_services = AsyncMock(return_value=([], []))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device.device_info, [], [])
    )

    # Simulate reconnection which triggers device registry update
    await device.mock_connect()
    await hass.async_block_till_done()

    # Verify device 2 was removed
    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, f"{device.device_info.mac_address}_11111111")}
        )
        is not None
    )
    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, f"{device.device_info.mac_address}_22222222")}
        )
        is None
    )  # Should be removed
    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, f"{device.device_info.mac_address}_33333333")}
        )
        is not None
    )


async def test_sub_device_with_empty_name(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test sub devices with empty names are handled correctly."""
    device_registry = dr.async_get(hass)

    # Define sub devices with empty names
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="", area_id=0),  # Empty name
        SubDeviceInfo(device_id=22222222, name="Valid Name", area_id=0),
    ]

    device_info = {
        "devices": sub_devices,
    }

    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
    )
    await hass.async_block_till_done()

    # Check sub device with empty name
    sub_device_1 = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{device.device_info.mac_address}_11111111")}
    )
    assert sub_device_1 is not None
    # Empty sub-device names should fall back to main device name
    main_device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, device.device_info.mac_address)}
    )
    assert sub_device_1.name == main_device.name

    # Check sub device with valid name
    sub_device_2 = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{device.device_info.mac_address}_22222222")}
    )
    assert sub_device_2 is not None
    assert sub_device_2.name == "Valid Name"


async def test_sub_device_references_main_device_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test sub devices can reference the main device's area."""
    device_registry = dr.async_get(hass)

    # Define areas - note we don't include area_id=0 in the areas list
    areas = [
        AreaInfo(area_id=1, name="Living Room"),
        AreaInfo(area_id=2, name="Bedroom"),
    ]

    # Define sub devices - one references the main device's area (area_id=0)
    sub_devices = [
        SubDeviceInfo(
            device_id=11111111, name="Motion Sensor", area_id=0
        ),  # Main device area
        SubDeviceInfo(
            device_id=22222222, name="Light Switch", area_id=1
        ),  # Living Room
        SubDeviceInfo(
            device_id=33333333, name="Temperature Sensor", area_id=2
        ),  # Bedroom
    ]

    device_info = {
        "areas": areas,
        "devices": sub_devices,
        "area": AreaInfo(area_id=0, name="Main Hub Area"),
    }

    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
    )

    # Check main device has correct area
    main_device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, device.device_info.mac_address)}
    )
    assert main_device is not None
    assert (
        main_device.area_id == area_registry.async_get_area_by_name("Main Hub Area").id
    )

    # Check sub device 1 uses main device's area
    sub_device_1 = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{device.device_info.mac_address}_11111111")}
    )
    assert sub_device_1 is not None
    assert (
        sub_device_1.area_id == area_registry.async_get_area_by_name("Main Hub Area").id
    )

    # Check sub device 2 uses Living Room
    sub_device_2 = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{device.device_info.mac_address}_22222222")}
    )
    assert sub_device_2 is not None
    assert (
        sub_device_2.area_id == area_registry.async_get_area_by_name("Living Room").id
    )

    # Check sub device 3 uses Bedroom
    sub_device_3 = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{device.device_info.mac_address}_33333333")}
    )
    assert sub_device_3 is not None
    assert sub_device_3.area_id == area_registry.async_get_area_by_name("Bedroom").id


@patch("homeassistant.components.esphome.manager.secrets.token_bytes")
async def test_dynamic_encryption_key_generation(
    mock_token_bytes: Mock,
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_storage: dict[str, Any],
) -> None:
    """Test that a device without a key in storage gets a new one generated."""
    mac_address = "11:22:33:44:55:aa"
    test_key_bytes = b"test_key_32_bytes_long_exactly!"
    mock_token_bytes.return_value = test_key_bytes
    expected_key = base64.b64encode(test_key_bytes).decode()

    # Create entry without noise PSK
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test-device",
        },
        unique_id=mac_address,
    )
    entry.add_to_hass(hass)

    # Mock the client methods
    mock_client.noise_encryption_set_key = AsyncMock(return_value=True)

    # Set up device with encryption support
    device = await mock_esphome_device(
        mock_client=mock_client,
        entry=entry,
        device_info={
            "uses_password": False,
            "name": "test-device",
            "mac_address": mac_address,
            "esphome_version": "2023.12.0",
            "api_encryption_supported": True,
        },
    )

    # Force reconnect to trigger key generation
    await device.mock_disconnect(True)
    await device.mock_connect()

    # Verify the key was generated and set
    mock_token_bytes.assert_called_once_with(32)
    mock_client.noise_encryption_set_key.assert_called_once()

    # Verify config entry was updated
    assert entry.data[CONF_NOISE_PSK] == expected_key


async def test_manager_retrieves_key_from_storage_on_reconnect(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_storage: dict[str, Any],
) -> None:
    """Test that manager retrieves encryption key from storage during reconnect."""
    mac_address = "11:22:33:44:55:aa"
    test_key = base64.b64encode(b"existing_key_32_bytes_long!!!").decode()

    # Set up storage with existing key
    hass_storage[ENCRYPTION_KEY_STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": ENCRYPTION_KEY_STORAGE_KEY,
        "data": {"keys": {mac_address: test_key}},
    }

    # Create entry without noise PSK (will be loaded from storage)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test-device",
        },
        unique_id=mac_address,
    )
    entry.add_to_hass(hass)

    # Mock the client methods
    mock_client.noise_encryption_set_key = AsyncMock(return_value=True)

    # Set up device with encryption support
    device = await mock_esphome_device(
        mock_client=mock_client,
        entry=entry,
        device_info={
            "uses_password": False,
            "name": "test-device",
            "mac_address": mac_address,
            "esphome_version": "2023.12.0",
            "api_encryption_supported": True,
        },
    )

    # Force reconnect to trigger key retrieval from storage
    await device.mock_disconnect(True)
    await device.mock_connect()

    # Verify noise_encryption_set_key was called with the stored key
    mock_client.noise_encryption_set_key.assert_called_once_with(test_key.encode())

    # Verify config entry was updated with key from storage
    assert entry.data[CONF_NOISE_PSK] == test_key


async def test_manager_handle_dynamic_encryption_key_guard_clauses(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test _handle_dynamic_encryption_key guard clauses and early returns."""
    # Test guard clause - no unique_id
    entry_no_id = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test-device",
        },
        unique_id=None,  # No unique ID - should not generate key
    )
    entry_no_id.add_to_hass(hass)

    # Set up device without unique ID
    device = await mock_esphome_device(
        mock_client=mock_client,
        entry=entry_no_id,
        device_info={
            "uses_password": False,
            "name": "test-device",
            "mac_address": "11:22:33:44:55:aa",
            "esphome_version": "2023.12.0",
            "api_encryption_supported": True,
        },
    )

    # noise_encryption_set_key should not be called when no unique_id
    mock_client.noise_encryption_set_key = AsyncMock()
    await device.mock_disconnect(True)
    await device.mock_connect()

    mock_client.noise_encryption_set_key.assert_not_called()


async def test_manager_handle_dynamic_encryption_key_edge_cases(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test _handle_dynamic_encryption_key edge cases for better coverage."""
    mac_address = "11:22:33:44:55:aa"

    # Test device without encryption support
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test-device",
        },
        unique_id=mac_address,
    )
    entry.add_to_hass(hass)

    # Set up device without encryption support
    device = await mock_esphome_device(
        mock_client=mock_client,
        entry=entry,
        device_info={
            "uses_password": False,
            "name": "test-device",
            "mac_address": mac_address,
            "esphome_version": "2023.12.0",
            "api_encryption_supported": False,  # No encryption support
        },
    )

    # noise_encryption_set_key should not be called when encryption not supported
    mock_client.noise_encryption_set_key = AsyncMock()
    await device.mock_disconnect(True)
    await device.mock_connect()

    mock_client.noise_encryption_set_key.assert_not_called()


@patch("homeassistant.components.esphome.manager.secrets.token_bytes")
async def test_manager_dynamic_encryption_key_generation_flow(
    mock_token_bytes: Mock,
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_storage: dict[str, Any],
) -> None:
    """Test the complete dynamic encryption key generation flow."""
    mac_address = "11:22:33:44:55:aa"
    test_key_bytes = b"test_key_32_bytes_long_exactly!"
    mock_token_bytes.return_value = test_key_bytes
    expected_key = base64.b64encode(test_key_bytes).decode()

    # Initialize empty storage
    hass_storage[ENCRYPTION_KEY_STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": ENCRYPTION_KEY_STORAGE_KEY,
        "data": {
            "keys": {}  # No existing keys
        },
    }

    # Create entry without noise PSK
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test-device",
        },
        unique_id=mac_address,
    )
    entry.add_to_hass(hass)

    # Mock the client methods
    mock_client.noise_encryption_set_key = AsyncMock(return_value=True)

    # Set up device with encryption support
    device = await mock_esphome_device(
        mock_client=mock_client,
        entry=entry,
        device_info={
            "uses_password": False,
            "name": "test-device",
            "mac_address": mac_address,
            "esphome_version": "2023.12.0",
            "api_encryption_supported": True,
        },
    )

    # Force reconnect to trigger key generation
    await device.mock_disconnect(True)
    await device.mock_connect()

    # Verify the complete flow
    mock_token_bytes.assert_called_once_with(32)
    mock_client.noise_encryption_set_key.assert_called_once()
    assert entry.data[CONF_NOISE_PSK] == expected_key

    # Verify key was stored in hass_storage
    assert (
        hass_storage[ENCRYPTION_KEY_STORAGE_KEY]["data"]["keys"][mac_address]
        == expected_key
    )


@patch("homeassistant.components.esphome.manager.secrets.token_bytes")
async def test_manager_handle_dynamic_encryption_key_no_existing_key(
    mock_token_bytes: Mock,
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_storage: dict[str, Any],
) -> None:
    """Test _handle_dynamic_encryption_key when no existing key is found."""
    mac_address = "11:22:33:44:55:aa"
    test_key_bytes = b"test_key_32_bytes_long_exactly!"
    mock_token_bytes.return_value = test_key_bytes
    expected_key = base64.b64encode(test_key_bytes).decode()

    # Initialize empty storage
    hass_storage[ENCRYPTION_KEY_STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": ENCRYPTION_KEY_STORAGE_KEY,
        "data": {
            "keys": {}  # No existing keys
        },
    }

    # Create entry without noise PSK
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test-device",
        },
        unique_id=mac_address,
    )
    entry.add_to_hass(hass)

    # Mock the client methods
    mock_client.noise_encryption_set_key = AsyncMock(return_value=True)

    # Set up device with encryption support
    device = await mock_esphome_device(
        mock_client=mock_client,
        entry=entry,
        device_info={
            "uses_password": False,
            "name": "test-device",
            "mac_address": mac_address,
            "esphome_version": "2023.12.0",
            "api_encryption_supported": True,
        },
    )

    # Force reconnect to trigger key generation
    await device.mock_disconnect(True)
    await device.mock_connect()

    # Verify key generation flow
    mock_token_bytes.assert_called_once_with(32)
    mock_client.noise_encryption_set_key.assert_called_once()

    # Verify config entry was updated
    assert entry.data[CONF_NOISE_PSK] == expected_key

    # Verify key was stored
    assert (
        hass_storage[ENCRYPTION_KEY_STORAGE_KEY]["data"]["keys"][mac_address]
        == expected_key
    )


@patch("homeassistant.components.esphome.manager.secrets.token_bytes")
async def test_manager_handle_dynamic_encryption_key_device_set_key_fails(
    mock_token_bytes: Mock,
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_storage: dict[str, Any],
) -> None:
    """Test _handle_dynamic_encryption_key when noise_encryption_set_key returns False."""
    mac_address = "11:22:33:44:55:aa"
    test_key_bytes = b"test_key_32_bytes_long_exactly!"
    mock_token_bytes.return_value = test_key_bytes

    # Initialize empty storage
    hass_storage[ENCRYPTION_KEY_STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": ENCRYPTION_KEY_STORAGE_KEY,
        "data": {
            "keys": {}  # No existing keys
        },
    }

    # Create entry without noise PSK
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test-device",
        },
        unique_id=mac_address,
    )
    entry.add_to_hass(hass)

    # Mock the client methods - set_key returns False
    mock_client.noise_encryption_set_key = AsyncMock(return_value=False)

    # Set up device with encryption support
    device = await mock_esphome_device(
        mock_client=mock_client,
        entry=entry,
        device_info={
            "uses_password": False,
            "name": "test-device",
            "mac_address": mac_address,
            "esphome_version": "2023.12.0",
            "api_encryption_supported": True,
        },
    )

    # Reset mocks since initial connection already happened
    mock_token_bytes.reset_mock()
    mock_client.noise_encryption_set_key.reset_mock()

    # Force reconnect to trigger key generation
    await device.mock_disconnect(True)
    await device.mock_connect()

    # Verify key generation was attempted with the expected key
    mock_token_bytes.assert_called_once_with(32)
    mock_client.noise_encryption_set_key.assert_called_once_with(
        base64.b64encode(test_key_bytes)
    )

    # Verify config entry was NOT updated since set_key failed
    assert CONF_NOISE_PSK not in entry.data


@patch("homeassistant.components.esphome.manager.secrets.token_bytes")
async def test_manager_handle_dynamic_encryption_key_connection_error(
    mock_token_bytes: Mock,
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_storage: dict[str, Any],
) -> None:
    """Test _handle_dynamic_encryption_key when noise_encryption_set_key raises APIConnectionError."""
    mac_address = "11:22:33:44:55:aa"
    test_key_bytes = b"test_key_32_bytes_long_exactly!"
    mock_token_bytes.return_value = test_key_bytes

    # Initialize empty storage
    hass_storage[ENCRYPTION_KEY_STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": ENCRYPTION_KEY_STORAGE_KEY,
        "data": {
            "keys": {}  # No existing keys
        },
    }

    # Create entry without noise PSK
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test-device",
        },
        unique_id=mac_address,
    )
    entry.add_to_hass(hass)

    # Mock the client methods - set_key raises APIConnectionError
    mock_client.noise_encryption_set_key = AsyncMock(
        side_effect=APIConnectionError("Connection failed")
    )

    # Set up device with encryption support
    device = await mock_esphome_device(
        mock_client=mock_client,
        entry=entry,
        device_info={
            "uses_password": False,
            "name": "test-device",
            "mac_address": mac_address,
            "esphome_version": "2023.12.0",
            "api_encryption_supported": True,
        },
    )

    # Force reconnect to trigger key generation
    await device.mock_disconnect(True)
    await device.mock_connect()

    # Verify key generation was attempted twice (once during setup, once during reconnect)
    # This is expected because the first attempt failed with connection error
    assert mock_token_bytes.call_count == 2
    mock_token_bytes.assert_called_with(32)
    assert mock_client.noise_encryption_set_key.call_count == 2

    # Verify config entry was NOT updated since connection error occurred
    assert CONF_NOISE_PSK not in entry.data

    # Verify key was NOT stored due to connection error
    assert mac_address not in hass_storage[ENCRYPTION_KEY_STORAGE_KEY]["data"]["keys"]


async def test_zwave_proxy_request_home_id_change(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test Z-Wave proxy request handler with HOME_ID_CHANGE request."""

    device_info = {
        "name": "test-zwave-proxy",
        "mac_address": "11:22:33:44:55:AA",
        "zwave_proxy_feature_flags": 1,
    }

    await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
    )
    await hass.async_block_till_done()

    # Get the manager's _async_zwave_proxy_request callback
    # It's registered via subscribe_zwave_proxy_request
    zwave_proxy_callback = None
    for call_item in mock_client.subscribe_zwave_proxy_request.call_args_list:
        if call_item[0]:
            zwave_proxy_callback = call_item[0][0]
            break

    assert zwave_proxy_callback is not None

    # Create a mock request with a different type (not HOME_ID_CHANGE)
    # Assuming there are other types, we'll use a placeholder value
    request = ZWaveProxyRequest(
        type=0,  # Not HOME_ID_CHANGE
        data=b"\x00\x00\x00\x01",
    )

    # Track flow creation
    with patch(
        "homeassistant.helpers.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        # Call the callback
        zwave_proxy_callback(request)
        await hass.async_block_till_done()

        # Verify no flow was created for non-HOME_ID_CHANGE requests
        mock_create_flow.assert_not_called()

    # Create a mock request with HOME_ID_CHANGE type and zwave_home_id as bytes
    zwave_home_id = 1234567890
    request = ZWaveProxyRequest(
        type=ZWaveProxyRequestType.HOME_ID_CHANGE,
        data=zwave_home_id.to_bytes(4, byteorder="big")
        + b"\x00\x00",  # Extra bytes should be ignored
    )

    # Track flow creation
    with patch(
        "homeassistant.helpers.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        # Call the callback
        zwave_proxy_callback(request)
        await hass.async_block_till_done()

        # Verify async_create_zwave_js_flow was called with correct arguments
        mock_create_flow.assert_called_once()
        call_args = mock_create_flow.call_args
        assert call_args[0][0] == hass
        assert call_args[0][1] == "zwave_js"


async def test_no_zwave_proxy_subscribe_without_feature_flags(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test Z-Wave proxy request subscription is not registered without feature flags."""
    device_info = {
        "name": "test-device",
        "mac_address": "11:22:33:44:55:AA",
        "zwave_proxy_feature_flags": 0,  # No Z-Wave proxy features
    }

    # Mock the subscribe_zwave_proxy_request method
    mock_client.subscribe_zwave_proxy_request = Mock(return_value=lambda: None)

    await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
    )
    await hass.async_block_till_done()

    # Verify subscribe_zwave_proxy_request was NOT called
    mock_client.subscribe_zwave_proxy_request.assert_not_called()
