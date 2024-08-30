"""Test ESPHome manager."""

import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, call

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    DeviceInfo,
    EntityInfo,
    EntityState,
    HomeassistantServiceCall,
    InvalidAuthAPIError,
    InvalidEncryptionKeyAPIError,
    RequiresEncryptionAPIError,
    UserService,
    UserServiceArg,
    UserServiceArgType,
)
import pytest

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.esphome.const import (
    CONF_ALLOW_SERVICE_CALLS,
    CONF_DEVICE_NAME,
    DOMAIN,
    STABLE_BLE_VERSION_STR,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    EVENT_HOMEASSISTANT_CLOSE,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import MockESPHomeDevice

from tests.common import MockConfigEntry, async_capture_events, async_mock_service


async def test_esphome_device_service_calls_not_allowed(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a device with service calls not allowed."""
    entity_info = []
    states = []
    user_service = []
    device: MockESPHomeDevice = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
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
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a device with service calls are allowed."""
    await async_setup_component(hass, "tag", {})
    entity_info = []
    states = []
    user_service = []
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ALLOW_SERVICE_CALLS: True}
    )
    device: MockESPHomeDevice = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
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


async def test_esphome_device_with_old_bluetooth(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a device with old bluetooth creates an issue."""
    entity_info = []
    states = []
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
        device_info={"bluetooth_proxy_feature_flags": 1, "esphome_version": "2023.3.0"},
    )
    await hass.async_block_till_done()
    issue = issue_registry.async_get_issue(
        "esphome", "ble_firmware_outdated-11:22:33:44:55:AA"
    )
    assert (
        issue.learn_more_url
        == f"https://esphome.io/changelog/{STABLE_BLE_VERSION_STR}.html"
    )


async def test_esphome_device_with_password(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a device with legacy password creates an issue."""
    entity_info = []
    states = []
    user_service = []

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
        entity_info=entity_info,
        user_service=user_service,
        states=states,
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
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a device with recent bluetooth does not create an issue."""
    entity_info = []
    states = []
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
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
async def test_unique_id_updated_to_mac(hass: HomeAssistant, mock_client) -> None:
    """Test we update config entry unique ID to MAC address."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="mock-config-name",
    )
    entry.add_to_hass(hass)
    subscribe_done = hass.loop.create_future()

    def async_subscribe_states(*args, **kwargs) -> None:
        subscribe_done.set_result(None)

    mock_client.subscribe_states = async_subscribe_states
    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(
            mac_address="1122334455aa",
        )
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async with asyncio.timeout(1):
        await subscribe_done

    assert entry.unique_id == "11:22:33:44:55:aa"


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
    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(mac_address="1122334455ab", name="test")
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
    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(mac_address="1122334455ab", name="test")
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
    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(mac_address="1122334455ab", name="different")
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

    def async_subscribe_states(*args, **kwargs) -> None:
        subscribe_done.set_result(None)

    mock_client.subscribe_states = async_subscribe_states
    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(mac_address="1122334455aa", name="new")
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

    def async_subscribe_states(*args, **kwargs) -> None:
        subscribe_done.set_result(None)

    mock_client.subscribe_states = async_subscribe_states
    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(mac_address="1122334455aa", name="new")
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
    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(mac_address="1122334455ab", name="different")
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

    assert "Error getting setting up connection for" not in caplog.text
    mock_client.disconnect = AsyncMock()
    caplog.clear()
    # Make sure discovery triggers a reconnect
    service_info = dhcp.DhcpServiceInfo(
        ip="192.168.43.184",
        hostname="test",
        macaddress="1122334455aa",
    )
    new_info = AsyncMock(
        return_value=DeviceInfo(mac_address="1122334455aa", name="test")
    )
    mock_client.device_info = new_info
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_DHCP}, data=service_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.43.184"
    await hass.async_block_till_done()
    assert len(new_info.mock_calls) == 1
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

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async with asyncio.timeout(1):
        await disconnect_done

    assert "Error getting setting up connection for" in caplog.text


async def test_state_subscription(
    mock_client: APIClient,
    hass: HomeAssistant,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test ESPHome subscribes to state changes."""
    device: MockESPHomeDevice = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
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
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test ESPHome requests state change."""
    device: MockESPHomeDevice = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
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
    mock_generic_device_entry: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockConfigEntry],
    ],
) -> None:
    """Test enabling and disabling debug logging."""
    assert await async_setup_component(hass, "logger", {"logger": {}})
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
    )
    await hass.services.async_call(
        "logger",
        "set_level",
        {"homeassistant.components.esphome": "DEBUG"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_client.set_debug.assert_has_calls([call(True)])

    mock_client.reset_mock()
    await hass.services.async_call(
        "logger",
        "set_level",
        {"homeassistant.components.esphome": "WARNING"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_client.set_debug.assert_has_calls([call(False)])


async def test_esphome_device_with_dash_in_name_user_services(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a device with user services and a dash in the name."""
    entity_info = []
    states = []
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
        entity_info=entity_info,
        user_service=[service1, service2],
        device_info={"name": "with-dash"},
        states=states,
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
    mock_client.list_entities_services = AsyncMock(
        return_value=(entity_info, [service1])
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
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a device with user services and a dash in the name."""
    entity_info = []
    states = []
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
        entity_info=entity_info,
        user_service=[service1, service2],
        device_info={"name": "with-dash"},
        states=states,
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
    mock_client.list_entities_services = AsyncMock(
        return_value=(entity_info, [service2])
    )
    await device.mock_disconnect(True)
    await hass.async_block_till_done()
    await device.mock_connect()
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "with_dash_simple_service")
    assert not hass.services.has_service(DOMAIN, "with_dash_bad_service")


async def test_esphome_user_services_changes(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a device with user services that change arguments."""
    entity_info = []
    states = []
    service1 = UserService(
        name="simple_service",
        key=2,
        args=[
            UserServiceArg(name="arg1", type=UserServiceArgType.BOOL),
        ],
    )
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=[service1],
        device_info={"name": "with-dash"},
        states=states,
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
    mock_client.list_entities_services = AsyncMock(
        return_value=(entity_info, [new_service1])
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
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a device with suggested area."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        device_info={"suggested_area": "kitchen"},
        states=[],
    )
    await hass.async_block_till_done()
    entry = device.entry
    dev = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, entry.unique_id)}
    )
    assert dev.suggested_area == "kitchen"


async def test_esphome_device_with_project(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a device with a project."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        device_info={"project_name": "mfr.model", "project_version": "2.2.2"},
        states=[],
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
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a device with a manufacturer."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        device_info={"manufacturer": "acme"},
        states=[],
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
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a device with a web server."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        device_info={"webserver_port": 80},
        states=[],
    )
    await hass.async_block_till_done()
    entry = device.entry
    dev = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, entry.unique_id)}
    )
    assert dev.configuration_url == "http://test.local:80"


async def test_esphome_device_with_compilation_time(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a device with a compilation_time."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        device_info={"compilation_time": "comp_time"},
        states=[],
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
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test the device is disconnected at the close event."""
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        device_info={"compilation_time": "comp_time"},
        states=[],
    )
    await hass.async_block_till_done()

    assert mock_client.disconnect.call_count == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()
    assert mock_client.disconnect.call_count == 1


@pytest.mark.parametrize(
    "error",
    [
        RequiresEncryptionAPIError,
        InvalidEncryptionKeyAPIError,
        InvalidAuthAPIError,
    ],
)
async def test_start_reauth(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    error: Exception,
) -> None:
    """Test exceptions on connect error trigger reauth."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        device_info={"compilation_time": "comp_time"},
        states=[],
    )
    await hass.async_block_till_done()

    await device.mock_connect_error(error("fail"))
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress(DOMAIN)
    assert len(flows) == 1
    flow = flows[0]
    assert flow["context"]["source"] == "reauth"


async def test_entry_missing_unique_id(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
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
