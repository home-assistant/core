"""Tests for Fritz!Tools coordinator."""

from __future__ import annotations

from collections.abc import Generator
from copy import deepcopy
from typing import cast
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzConnectionException,
    FritzSecurityError,
)
from fritzconnection.lib.fritztools import ArgumentNamespace
import pytest

from homeassistant.components.fritz.const import (
    CONF_FEATURE_DEVICE_TRACKING,
    DEFAULT_CONF_FEATURE_DEVICE_TRACKING,
    DEFAULT_SSL,
    DOMAIN,
)
from homeassistant.components.fritz.coordinator import (
    AvmWrapper,
    ClassSetupMissing,
    FritzBoxTools,
    FritzConnectionCached,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .conftest import FritzConnectionMock, FritzServiceMock
from .const import MOCK_MESH_MASTER_MAC, MOCK_STATUS_DEVICE_INFO_DATA, MOCK_USER_DATA

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_config_entry")
def fixture_mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry with host, username, password, and port."""

    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        unique_id="1234",
    )


@pytest.fixture
def patch_fritzconnectioncached_globally(fc_data) -> Generator[FritzConnectionMock]:
    """Patch FritzConnectionCached globally for coordinator-only tests."""

    mock_conn = FritzConnectionMock(fc_data)
    with patch(
        "homeassistant.components.fritz.coordinator.FritzConnectionCached",
        return_value=mock_conn,
    ):
        yield mock_conn


@pytest.fixture(name="fritz_tools")
async def fixture_fritz_tools(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_fritzconnectioncached_globally: FritzConnectionMock,
) -> FritzBoxTools:
    """Return FritzBoxTools instance with mocked connection."""

    mock_config_entry.add_to_hass(hass)
    coordinator = FritzBoxTools(
        hass=hass,
        config_entry=mock_config_entry,
        password=mock_config_entry.data["password"],
        port=mock_config_entry.data["port"],
    )

    await coordinator.async_setup()
    return coordinator


@pytest.mark.parametrize(
    "attr",
    [
        "unique_id",
        "model",
        "current_firmware",
        "mac",
    ],
)
async def test_fritzboxtools_class_no_setup(
    hass: HomeAssistant,
    attr: str,
) -> None:
    """Test accessing FritzBoxTools class properties before setup."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    coordinator = AvmWrapper(
        hass=hass,
        config_entry=entry,
        host=MOCK_USER_DATA[CONF_HOST],
        port=MOCK_USER_DATA[CONF_PORT],
        username=MOCK_USER_DATA[CONF_USERNAME],
        password=MOCK_USER_DATA[CONF_PASSWORD],
        use_tls=MOCK_USER_DATA.get(CONF_SSL, DEFAULT_SSL),
        device_discovery_enabled=MOCK_USER_DATA.get(
            CONF_FEATURE_DEVICE_TRACKING, DEFAULT_CONF_FEATURE_DEVICE_TRACKING
        ),
    )

    with pytest.raises(ClassSetupMissing):
        getattr(coordinator, attr)


async def test_clear_connection_cache(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test clearing the connection cache."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED

    caplog.clear()
    fc_class_mock.return_value.clear_cache()

    assert "Cleared FritzConnection call action cache" in caplog.text


async def test_no_connection(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test no connection established."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.coordinator.FritzConnectionCached",
        return_value=None,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert (
            f"Unable to establish a connection with {MOCK_USER_DATA[CONF_HOST]}"
            in caplog.text
        )


async def test_no_software_version(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test software version non normalized."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    device_info = deepcopy(MOCK_STATUS_DEVICE_INFO_DATA)
    device_info["NewSoftwareVersion"] = "string_version_not_number"
    with patch.object(
        fs_class_mock,
        "get_device_info",
        MagicMock(return_value=ArgumentNamespace(device_info)),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_MESH_MASTER_MAC)}
    )
    assert device
    assert device.sw_version == "string_version_not_number"


async def test_connection_cached_call_action() -> None:
    """Test call_action cache behavior for get and non-get actions."""

    conn = object.__new__(FritzConnectionCached)

    with patch(
        "homeassistant.components.fritz.coordinator.FritzConnection.call_action",
        autospec=True,
        return_value={"ok": True},
    ) as parent_call:
        first = conn.call_action("Svc", "GetInfo", arguments={"a": 1})
        second = conn.call_action("Svc", "GetInfo", arguments={"a": 1})
        assert first == {"ok": True}
        assert second == first
        assert parent_call.call_count == 1

        conn.clear_cache()
        third = conn.call_action("Svc", "GetInfo", arguments={"a": 1})
        assert third == first
        assert parent_call.call_count == 2

        conn.call_action("Svc", "SetEnable", NewEnable="1")
        assert parent_call.call_count == 3


async def test_async_get_wan_access_error_returns_none(
    fritz_tools,
) -> None:
    """Test WAN access query error handling returns None."""

    cast(FritzConnectionMock, fritz_tools.connection).call_action_side_effect(
        FritzActionError("boom")
    )
    assert await fritz_tools._async_get_wan_access("192.168.1.2") is None


async def test_async_get_wan_access_success(
    fritz_tools,
) -> None:
    """Test WAN access query success path."""

    fritz_tools.connection.call_action = MagicMock(return_value={"NewDisallow": False})
    assert await fritz_tools._async_get_wan_access("192.168.1.2") is True


async def test_async_update_hosts_info_attributes_branches(
    fritz_tools,
) -> None:
    """Test host-attributes branch."""

    fritz_tools.fritz_hosts.get_hosts_attributes = MagicMock(
        return_value=[
            {
                "HostName": "printer",
                "Active": True,
                "IPAddress": "192.168.178.2",
                "MACAddress": "AA:BB:CC:DD:EE:01",
                "X_AVM-DE_WANAccess": "granted",
            },
            {
                "HostName": "server",
                "Active": False,
                "IPAddress": "192.168.178.3",
                "MACAddress": "AA:BB:CC:DD:EE:02",
            },
            {
                "HostName": "ignored",
                "Active": False,
                "IPAddress": "192.168.178.4",
                "MACAddress": "",
            },
        ]
    )

    hosts = await fritz_tools._async_update_hosts_info()
    assert set(hosts) == {"AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"}
    assert hosts["AA:BB:CC:DD:EE:01"].wan_access is True
    assert hosts["AA:BB:CC:DD:EE:02"].wan_access is None


async def test_async_update_hosts_info_hosts_info_fallback(
    fritz_tools,
) -> None:
    """Test hosts-info fallback branch after attribute action error."""

    fritz_tools.fritz_hosts.get_hosts_attributes = MagicMock(
        side_effect=FritzActionError("not supported")
    )
    fritz_tools.fritz_hosts.get_hosts_info = MagicMock(
        return_value=[
            {"name": "printer", "status": True, "ip": "192.168.178.2", "mac": "AA:BB"},
            {"name": "server", "status": False, "ip": "", "mac": "AA:CC"},
            {"name": "ignore", "status": False, "ip": "192.168.178.10", "mac": ""},
        ]
    )
    with patch.object(
        fritz_tools,
        "_async_get_wan_access",
        new=AsyncMock(return_value=False),
    ) as wan_access:
        hosts = await fritz_tools._async_update_hosts_info()

    assert set(hosts) == {"AA:BB", "AA:CC"}
    assert hosts["AA:BB"].wan_access is False
    assert hosts["AA:CC"].wan_access is None
    wan_access.assert_awaited_once_with("192.168.178.2")


async def test_async_update_hosts_info_raises_homeassistant_error(
    fritz_tools,
) -> None:
    """Test host update raises HomeAssistantError when API calls fail."""

    fritz_tools.fritz_hosts.get_hosts_attributes = MagicMock(
        side_effect=FritzActionError("not supported")
    )
    fritz_tools.fritz_hosts.get_hosts_info = MagicMock(
        side_effect=RuntimeError("broken")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await fritz_tools._async_update_hosts_info()

    assert exc_info.value.translation_key == "error_refresh_hosts_info"


async def test_async_update_call_deflections_empty_paths(
    fritz_tools,
) -> None:
    """Test call deflections empty responses."""

    fritz_tools.connection.call_action = MagicMock(return_value={})
    assert await fritz_tools.async_update_call_deflections() == {}

    fritz_tools.connection.call_action = MagicMock(
        return_value={"NewDeflectionList": "<List><Foo>Bar</Foo></List>"}
    )
    assert await fritz_tools.async_update_call_deflections() == {}


async def test_async_scan_devices_stopping_returns(
    hass: HomeAssistant,
    fritz_tools,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test scan devices exits when Home Assistant is stopping."""

    with patch.object(hass, "is_stopping", True):
        await fritz_tools.async_scan_devices()

    assert "Cannot execute scan devices: HomeAssistant is shutting down" in caplog.text


async def test_async_scan_devices_old_discovery_branch(
    fritz_tools,
) -> None:
    """Test old discovery path when mesh support is unavailable."""

    hosts = {"AA:BB": MagicMock()}
    with (
        patch.object(
            type(fritz_tools.fritz_status),
            "device_has_mesh_support",
            new_callable=PropertyMock,
            return_value=False,
        ),
        patch.object(
            fritz_tools, "_async_update_hosts_info", AsyncMock(return_value=hosts)
        ),
        patch.object(fritz_tools, "manage_device_info", return_value=True),
        patch.object(
            fritz_tools, "async_send_signal_device_update", AsyncMock()
        ) as update,
    ):
        await fritz_tools.async_scan_devices()

    update.assert_awaited_once_with(True)


async def test_async_scan_devices_empty_mesh_topology_raises(
    fritz_tools,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test empty mesh topology raises as expected."""

    with (
        patch.object(
            type(fritz_tools.fritz_status),
            "device_has_mesh_support",
            new_callable=PropertyMock,
            return_value=True,
        ),
        patch.object(
            fritz_tools, "_async_update_hosts_info", AsyncMock(return_value={})
        ),
        patch.object(
            fritz_tools.fritz_hosts, "get_mesh_topology", MagicMock(return_value={})
        ),
        pytest.raises(Exception, match="Mesh supported but empty topology reported"),
    ):
        await fritz_tools.async_scan_devices()

    assert "ERROR" not in caplog.text


async def test_async_scan_devices_mesh_guest_and_missing_host(
    fritz_tools,
) -> None:
    """Test mesh client processing for AP guest and unknown hosts."""

    hosts = {"AA:BB:CC:DD:EE:01": MagicMock(wan_access=True)}
    topology = {
        "nodes": [
            {
                "is_meshed": True,
                "mesh_role": "master",
                "device_name": "fritz.box",
                "node_interfaces": [
                    {
                        "uid": "ap-guest",
                        "mac_address": fritz_tools.unique_id,
                        "op_mode": "AP_GUEST",
                        "ssid": "guest",
                        "type": "WLAN",
                        "name": "uplink0",
                        "node_links": [],
                    }
                ],
            },
            {
                "is_meshed": False,
                "node_interfaces": [
                    {
                        "mac_address": "AA:BB:CC:DD:EE:02",
                        "node_links": [
                            {"state": "CONNECTED", "node_interface_1_uid": "ap-guest"}
                        ],
                    },
                    {
                        "mac_address": "AA:BB:CC:DD:EE:01",
                        "node_links": [
                            {"state": "CONNECTED", "node_interface_1_uid": "ap-guest"}
                        ],
                    },
                ],
            },
        ]
    }

    with (
        patch.object(
            fritz_tools, "_async_update_hosts_info", AsyncMock(return_value=hosts)
        ),
        patch.object(
            fritz_tools.fritz_hosts,
            "get_mesh_topology",
            MagicMock(return_value=topology),
        ),
        patch.object(fritz_tools, "manage_device_info", return_value=False) as manage,
        patch.object(fritz_tools, "async_send_signal_device_update", AsyncMock()),
    ):
        await fritz_tools.async_scan_devices()

    dev_info = manage.call_args.args[0]
    assert dev_info.wan_access is None


async def test_trigger_methods(
    fritz_tools,
) -> None:
    """Test trigger methods delegate to correct underlying calls."""

    fritz_tools.connection.call_action = MagicMock(
        return_value={"NewX_AVM-DE_UpdateState": True}
    )
    fritz_tools.connection.reboot = MagicMock()
    fritz_tools.connection.reconnect = MagicMock()
    fritz_tools.fritz_guest_wifi.set_password = MagicMock()
    fritz_tools.fritz_call.dial = MagicMock()
    fritz_tools.fritz_call.hangup = MagicMock()

    assert await fritz_tools.async_trigger_firmware_update() is True
    await fritz_tools.async_trigger_reboot()
    await fritz_tools.async_trigger_reconnect()
    await fritz_tools.async_trigger_set_guest_password("new-password", 20)

    with patch(
        "homeassistant.components.fritz.coordinator.asyncio.sleep",
        new=AsyncMock(),
    ) as sleep_mock:
        await fritz_tools.async_trigger_dial("012345", 1)

    fritz_tools.connection.reboot.assert_called_once()
    fritz_tools.connection.reconnect.assert_called_once()
    fritz_tools.fritz_guest_wifi.set_password.assert_called_once_with(
        "new-password", 20
    )
    fritz_tools.fritz_call.dial.assert_called_once_with("012345")
    sleep_mock.assert_awaited_once_with(1)
    fritz_tools.fritz_call.hangup.assert_called_once()


async def test_avmwrapper_service_call_branches(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test AvmWrapper service call return and exception branches."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    wrapper = entry.runtime_data

    wrapper.connection.services.pop("Hosts1", None)
    assert await wrapper._async_service_call("Hosts", "1", "GetInfo") == {}
    wrapper.connection.services["Hosts1"] = FritzServiceMock(["GetInfo"])

    wrapper.connection.call_action = MagicMock(side_effect=FritzSecurityError("boom"))
    assert await wrapper._async_service_call("Hosts", "1", "GetInfo") == {}

    wrapper.connection.call_action = MagicMock(side_effect=FritzActionError("boom"))
    assert await wrapper._async_service_call("Hosts", "1", "GetInfo") == {}

    with patch.object(
        hass,
        "async_add_executor_job",
        new=AsyncMock(side_effect=FritzConnectionException("boom")),
    ):
        assert await wrapper._async_service_call("Hosts", "1", "GetInfo") == {}

    assert "cannot execute service Hosts with action GetInfo" in caplog.text


async def test_avmwrapper_passthrough_methods(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test AvmWrapper helper methods and service wrappers."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    wrapper = entry.runtime_data

    wrapper.device_is_router = False
    assert await wrapper.async_ipv6_active() is False

    assert await wrapper.async_set_wlan_configuration(1, True) == {}
    assert await wrapper.async_set_deflection_enable(1, False) == {}
    assert (
        await wrapper.async_add_port_mapping(
            "WANPPPConnection", {"NewExternalPort": 8080}
        )
        == {}
    )
    assert await wrapper.async_set_allow_wan_access("192.168.178.2", True) == {}
    assert await wrapper.async_wake_on_lan("AA:BB:CC:DD:EE:FF") == {}
