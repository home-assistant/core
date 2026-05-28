"""Test the Matter integration init."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, call, patch

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import PartialBackupOptions
from matter_server.client.exceptions import (
    CannotConnect,
    NotConnected,
    ServerVersionTooNew,
    ServerVersionTooOld,
)
from matter_server.common.errors import MatterError
import pytest

from homeassistant.components.matter import _derive_ble_proxy_url
from homeassistant.components.matter.const import DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .common import (
    FIXTURES,
    create_node_from_fixture,
    load_and_parse_node_fixture,
    setup_integration_with_node_fixture,
)

from tests.common import MockConfigEntry, mock_component
from tests.typing import WebSocketGenerator


@pytest.fixture(name="connect_timeout")
def connect_timeout_fixture() -> Generator[int]:
    """Mock the connect timeout."""
    with patch("homeassistant.components.matter.CONNECT_TIMEOUT", new=0) as timeout:
        yield timeout


@pytest.fixture(name="ble_proxy_connect_timeout")
def ble_proxy_connect_timeout_fixture() -> Generator[int]:
    """Shorten the BLE proxy connect timeout."""
    with patch(
        "homeassistant.components.matter.BLE_PROXY_CONNECT_TIMEOUT", new=0
    ) as timeout:
        yield timeout


@pytest.fixture(name="mock_bluetooth_loaded")
def mock_bluetooth_loaded_fixture(hass: HomeAssistant) -> None:
    """Mark the bluetooth integration as loaded for the BLE proxy gate."""
    mock_component(hass, "bluetooth")


@pytest.fixture(name="mock_ble_proxy")
def mock_ble_proxy_fixture() -> Generator[tuple[MagicMock, MagicMock]]:
    """Stub the BLE proxy created inside async_setup_entry.

    Yields `(proxy, factory)` so tests can assert both the proxy lifecycle
    (`connect`/`disconnect`) and the arguments passed to `create_matter_ble_proxy`.
    """
    proxy = MagicMock()
    proxy.connect = AsyncMock()
    proxy.disconnect = AsyncMock()
    with patch(
        "homeassistant.components.matter.ble_proxy.create_matter_ble_proxy",
        return_value=proxy,
    ) as factory:
        yield proxy, factory


@pytest.fixture(name="listen_ready_timeout")
def listen_ready_timeout_fixture() -> Generator[int]:
    """Mock the listen ready timeout."""
    with patch(
        "homeassistant.components.matter.LISTEN_READY_TIMEOUT", new=0
    ) as timeout:
        yield timeout


def test_fixture_list() -> None:
    """Test validity of the fixture list."""
    # Ensure it is sorted - makes it easier to identify duplicate entries or
    # locate specific fixtures
    assert sorted(FIXTURES) == FIXTURES, "Fixture list is not sorted"
    # Ensure all fixtures have a unique node id
    node_ids = set()
    for fixture in FIXTURES:
        node_data = load_and_parse_node_fixture(fixture)
        if (node_id := node_data["node_id"]) in node_ids:
            pytest.fail(
                f"Duplicate node ID {node_id} found in fixture {fixture}, "
                f"please use: {next(i for i in range(1, 1000) if i not in node_ids)}"
            )
        node_ids.add(node_id)


async def test_entry_setup_unload(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test the integration set up and unload."""
    node = create_node_from_fixture("mock_onoff_light")
    matter_client.get_nodes.return_value = [node]
    matter_client.get_node.return_value = node
    entry = MockConfigEntry(domain="matter", data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert matter_client.connect.call_count == 1
    assert matter_client.set_default_fabric_label.call_count == 1
    assert entry.state is ConfigEntryState.LOADED
    entity_state = hass.states.get("light.mock_onoff_light")
    assert entity_state
    assert entity_state.state != STATE_UNAVAILABLE

    await hass.config_entries.async_unload(entry.entry_id)

    assert matter_client.disconnect.call_count == 1
    assert entry.state is ConfigEntryState.NOT_LOADED
    entity_state = hass.states.get("light.mock_onoff_light")
    assert entity_state
    assert entity_state.state == STATE_UNAVAILABLE


async def test_home_assistant_stop(
    hass: HomeAssistant,
    matter_client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test clean up on home assistant stop."""
    await hass.async_stop()

    assert matter_client.disconnect.call_count == 1


@pytest.mark.parametrize("error", [CannotConnect(Exception("Boom")), Exception("Boom")])
async def test_connect_failed(
    hass: HomeAssistant,
    matter_client: MagicMock,
    error: Exception,
) -> None:
    """Test failure during client connection."""
    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)
    matter_client.connect.side_effect = error

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_set_default_fabric_label_failed(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test failure during client connection."""
    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)

    matter_client.set_default_fabric_label.side_effect = NotConnected()

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert matter_client.connect.call_count == 1
    assert matter_client.set_default_fabric_label.call_count == 1

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_connect_timeout(
    hass: HomeAssistant,
    matter_client: MagicMock,
    connect_timeout: int,
) -> None:
    """Test timeout during client connection."""
    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("error", [MatterError("Boom"), Exception("Boom")])
async def test_listen_failure_timeout(
    hass: HomeAssistant,
    listen_ready_timeout: int,
    matter_client: MagicMock,
    error: Exception,
) -> None:
    """Test client listen errors during the first timeout phase."""

    async def start_listening(listen_ready: asyncio.Event) -> None:
        """Mock the client start_listening method."""
        # Set the connect side effect to stop an endless loop on reload.
        matter_client.connect.side_effect = MatterError("Boom")
        raise error

    matter_client.start_listening.side_effect = start_listening
    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("error", [MatterError("Boom"), Exception("Boom")])
async def test_listen_failure_config_entry_not_loaded(
    hass: HomeAssistant,
    matter_client: MagicMock,
    error: Exception,
) -> None:
    """Test client listen errors during the final phase before config entry loaded."""
    listen_block = asyncio.Event()

    async def start_listening(listen_ready: asyncio.Event) -> None:
        """Mock the client start_listening method."""
        listen_ready.set()
        await listen_block.wait()
        # Set the connect side effect to stop an endless loop on reload.
        matter_client.connect.side_effect = MatterError("Boom")
        raise error

    def get_nodes() -> list[MagicMock]:
        """Mock the client get_nodes method."""
        listen_block.set()
        return []

    matter_client.start_listening.side_effect = start_listening
    matter_client.get_nodes.side_effect = get_nodes
    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert matter_client.disconnect.call_count == 1


@pytest.mark.parametrize("error", [MatterError("Boom"), Exception("Boom")])
async def test_listen_failure_config_entry_loaded(
    hass: HomeAssistant,
    matter_client: MagicMock,
    error: Exception,
) -> None:
    """Test client listen errors after config entry is loaded."""
    listen_block = asyncio.Event()

    async def start_listening(listen_ready: asyncio.Event) -> None:
        """Mock the client start_listening method."""
        listen_ready.set()
        await listen_block.wait()
        # Set the connect side effect to stop an endless loop on reload.
        matter_client.connect.side_effect = MatterError("Boom")
        raise error

    matter_client.start_listening.side_effect = start_listening
    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    listen_block.set()
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert matter_client.disconnect.call_count == 1


async def test_raise_addon_task_in_progress(
    hass: HomeAssistant, install_addon: AsyncMock, start_addon: AsyncMock
) -> None:
    """Test raise ConfigEntryNotReady if an add-on task is in progress."""
    install_event = asyncio.Event()

    install_addon_original_side_effect = install_addon.side_effect

    async def install_addon_side_effect(slug: str) -> None:
        """Mock install add-on."""
        await install_event.wait()
        await install_addon_original_side_effect(slug)

    install_addon.side_effect = install_addon_side_effect

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={
            "url": "ws://host1:5581/ws",
            "use_addon": True,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await asyncio.sleep(0.05)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert install_addon.call_count == 1
    assert start_addon.call_count == 0

    # Check that we only call install add-on once if a task is in progress.
    await hass.config_entries.async_reload(entry.entry_id)
    await asyncio.sleep(0.05)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert install_addon.call_count == 1
    assert start_addon.call_count == 0

    install_event.set()
    await hass.async_block_till_done()

    assert install_addon.call_count == 1
    assert start_addon.call_count == 1


async def test_start_addon(
    hass: HomeAssistant,
    addon_installed: AsyncMock,
    addon_info: AsyncMock,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test start the Matter Server add-on during entry setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={
            "url": "ws://host1:5581/ws",
            "use_addon": True,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert addon_info.call_count == 1
    assert install_addon.call_count == 0
    assert start_addon.call_count == 1
    assert start_addon.call_args == call("core_matter_server")


async def test_install_addon(
    hass: HomeAssistant,
    addon_store_info: AsyncMock,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test install and start the Matter add-on during entry setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={
            "url": "ws://host1:5581/ws",
            "use_addon": True,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert addon_store_info.call_count == 2
    assert install_addon.call_count == 1
    assert install_addon.call_args == call("core_matter_server")
    assert start_addon.call_count == 1
    assert start_addon.call_args == call("core_matter_server")


async def test_addon_info_failure(
    hass: HomeAssistant,
    addon_installed: AsyncMock,
    addon_info: AsyncMock,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test failure to get add-on info for Matter add-on during entry setup."""
    addon_info.side_effect = SupervisorError("Boom")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={
            "url": "ws://host1:5581/ws",
            "use_addon": True,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert addon_info.call_count == 1
    assert install_addon.call_count == 0
    assert start_addon.call_count == 0


@pytest.mark.parametrize(
    (
        "addon_version",
        "update_available",
        "update_calls",
        "backup_calls",
        "update_addon_side_effect",
        "create_backup_side_effect",
        "connect_side_effect",
    ),
    [
        ("1.0.0", True, 1, 1, None, None, ServerVersionTooOld("Invalid version")),
        ("1.0.0", True, 0, 0, None, None, ServerVersionTooNew("Invalid version")),
        ("1.0.0", False, 0, 0, None, None, ServerVersionTooOld("Invalid version")),
        (
            "1.0.0",
            True,
            1,
            1,
            SupervisorError("Boom"),
            None,
            ServerVersionTooOld("Invalid version"),
        ),
        (
            "1.0.0",
            True,
            0,
            1,
            None,
            SupervisorError("Boom"),
            ServerVersionTooOld("Invalid version"),
        ),
    ],
)
async def test_update_addon(
    hass: HomeAssistant,
    addon_installed: AsyncMock,
    addon_running: AsyncMock,
    addon_info: AsyncMock,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
    create_backup: AsyncMock,
    update_addon: AsyncMock,
    matter_client: MagicMock,
    addon_version: str,
    update_available: bool,
    update_calls: int,
    backup_calls: int,
    update_addon_side_effect: Exception | None,
    create_backup_side_effect: Exception | None,
    connect_side_effect: Exception,
) -> None:
    """Test update the Matter add-on during entry setup."""
    addon_info.return_value.version = addon_version
    addon_info.return_value.update_available = update_available
    create_backup.side_effect = create_backup_side_effect
    update_addon.side_effect = update_addon_side_effect
    matter_client.connect.side_effect = connect_side_effect
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={
            "url": "ws://host1:5581/ws",
            "use_addon": True,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert create_backup.call_count == backup_calls
    assert update_addon.call_count == update_calls


@pytest.mark.parametrize(
    (
        "connect_side_effect",
        "issue_raised",
    ),
    [
        (
            ServerVersionTooOld("Invalid version"),
            "server_version_version_too_old",
        ),
        (
            ServerVersionTooNew("Invalid version"),
            "server_version_version_too_new",
        ),
    ],
)
async def test_issue_registry_invalid_version(
    hass: HomeAssistant,
    matter_client: MagicMock,
    issue_registry: ir.IssueRegistry,
    connect_side_effect: Exception,
    issue_raised: str,
) -> None:
    """Test issue registry for invalid version."""
    original_connect_side_effect = matter_client.connect.side_effect
    matter_client.connect.side_effect = connect_side_effect
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={
            "url": "ws://host1:5581/ws",
            "use_addon": False,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entry_state = entry.state
    assert entry_state is ConfigEntryState.SETUP_RETRY
    assert issue_registry.async_get_issue(DOMAIN, issue_raised)

    matter_client.connect.side_effect = original_connect_side_effect

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert not issue_registry.async_get_issue(DOMAIN, issue_raised)


@pytest.mark.parametrize(
    ("stop_addon_side_effect", "entry_state"),
    [
        (None, ConfigEntryState.NOT_LOADED),
        (SupervisorError("Boom"), ConfigEntryState.FAILED_UNLOAD),
    ],
)
async def test_stop_addon(
    hass: HomeAssistant,
    matter_client: MagicMock,
    addon_installed: AsyncMock,
    addon_running: AsyncMock,
    addon_info: AsyncMock,
    stop_addon: AsyncMock,
    stop_addon_side_effect: Exception | None,
    entry_state: ConfigEntryState,
) -> None:
    """Test stop the Matter add-on on entry unload if entry is disabled."""
    stop_addon.side_effect = stop_addon_side_effect
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={
            "url": "ws://host1:5581/ws",
            "use_addon": True,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert addon_info.call_count == 1
    addon_info.reset_mock()

    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert entry.state is entry_state
    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call("core_matter_server")


async def test_remove_entry(
    hass: HomeAssistant,
    addon_installed: AsyncMock,
    stop_addon: AsyncMock,
    create_backup: AsyncMock,
    uninstall_addon: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test remove the config entry."""
    # test successful remove without created add-on
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={"integration_created_addon": False},
    )
    entry.add_to_hass(hass)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    await hass.config_entries.async_remove(entry.entry_id)

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0

    # test successful remove with created add-on
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={"integration_created_addon": True},
    )
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call("core_matter_server")
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        PartialBackupOptions(
            name="addon_core_matter_server_1.0.0", addons={"core_matter_server"}
        ),
    )
    assert uninstall_addon.call_count == 1
    assert uninstall_addon.call_args == call("core_matter_server")
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    stop_addon.reset_mock()
    create_backup.reset_mock()
    uninstall_addon.reset_mock()

    # test add-on stop failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    stop_addon.side_effect = SupervisorError()

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call("core_matter_server")
    assert create_backup.call_count == 0
    assert uninstall_addon.call_count == 0
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to stop the Matter Server app" in caplog.text
    stop_addon.side_effect = None
    stop_addon.reset_mock()
    create_backup.reset_mock()
    uninstall_addon.reset_mock()

    # test create backup failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    create_backup.side_effect = SupervisorError()

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call("core_matter_server")
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        PartialBackupOptions(
            name="addon_core_matter_server_1.0.0", addons={"core_matter_server"}
        ),
    )
    assert uninstall_addon.call_count == 0
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to create a backup of the Matter Server app" in caplog.text
    create_backup.side_effect = None
    stop_addon.reset_mock()
    create_backup.reset_mock()
    uninstall_addon.reset_mock()

    # test add-on uninstall failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    uninstall_addon.side_effect = SupervisorError()

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call("core_matter_server")
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        PartialBackupOptions(
            name="addon_core_matter_server_1.0.0", addons={"core_matter_server"}
        ),
    )
    assert uninstall_addon.call_count == 1
    assert uninstall_addon.call_args == call("core_matter_server")
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to uninstall the Matter Server app" in caplog.text


async def test_remove_config_entry_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that a device can be removed ok."""
    assert await async_setup_component(hass, "config", {})
    await setup_integration_with_node_fixture(hass, "device_diagnostics", matter_client)
    await hass.async_block_till_done()

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    device_entry = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )[0]
    entity_id = "light.m5stamp_lighting_app"

    assert device_entry
    assert entity_registry.async_get(entity_id)
    assert hass.states.get(entity_id)

    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id, config_entry.entry_id)
    assert response["success"]
    await hass.async_block_till_done()

    assert not device_registry.async_get(device_entry.id)
    assert not entity_registry.async_get(entity_id)
    assert not hass.states.get(entity_id)


async def test_remove_config_entry_device_no_node(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
    integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that a device can be removed ok without an existing node."""
    assert await async_setup_component(hass, "config", {})
    config_entry = integration
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000005-MatterNodeDevice")
        },
    )

    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id, config_entry.entry_id)
    assert response["success"]
    await hass.async_block_till_done()

    assert not device_registry.async_get(device_entry.id)


@pytest.mark.parametrize(
    ("matter_ws_url", "expected"),
    [
        ("ws://localhost:5580/ws", "ws://localhost:5580/ble"),
        ("wss://example.com/ws", "wss://example.com/ble"),
        ("ws://localhost:5580/", "ws://localhost:5580/ble"),
        ("ws://localhost:5580", "ws://localhost:5580/ble"),
        ("ws://ws.example.com:5580/ws", "ws://ws.example.com:5580/ble"),
        ("ws://localhost:5580/custom/ws", "ws://localhost:5580/custom/ble"),
        ("ws://localhost:5580/api", None),
        ("ws://localhost:5580/matter", None),
    ],
)
def test_derive_ble_proxy_url(matter_ws_url: str, expected: str | None) -> None:
    """Derived /ble URL preserves scheme/host/port and only swaps the trailing path.

    Returns None when the path does not match the expected `/ws` shape.
    """
    assert _derive_ble_proxy_url(matter_ws_url) == expected


@pytest.mark.usefixtures("mock_bluetooth_loaded")
async def test_ble_proxy_setup_when_enabled(
    hass: HomeAssistant,
    matter_client: MagicMock,
    mock_ble_proxy: tuple[MagicMock, MagicMock],
) -> None:
    """BLE proxy is created with the derived `/ble` URL and connected."""
    proxy, factory = mock_ble_proxy
    matter_client.server_info.ble_proxy_enabled = True

    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    factory.assert_called_once_with(hass, "ws://localhost:5580/ble")
    proxy.connect.assert_awaited_once()
    assert entry.runtime_data.ble_proxy is proxy

    await hass.config_entries.async_unload(entry.entry_id)
    proxy.disconnect.assert_awaited()


@pytest.mark.usefixtures("mock_bluetooth_loaded")
async def test_ble_proxy_disconnects_on_setup_failure(
    hass: HomeAssistant,
    matter_client: MagicMock,
    mock_ble_proxy: tuple[MagicMock, MagicMock],
) -> None:
    """BLE proxy + matter_client are disconnected when setup raises after connect."""
    proxy, _factory = mock_ble_proxy
    matter_client.server_info.ble_proxy_enabled = True

    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.matter.MatterAdapter.setup_nodes",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    proxy.connect.assert_awaited_once()
    proxy.disconnect.assert_awaited_once()
    matter_client.disconnect.assert_awaited()


@pytest.mark.usefixtures("mock_bluetooth_loaded")
async def test_ble_proxy_disconnect_on_hass_stop(
    hass: HomeAssistant,
    matter_client: MagicMock,
    mock_ble_proxy: tuple[MagicMock, MagicMock],
) -> None:
    """BLE proxy is disconnected when Home Assistant stops."""
    proxy, _factory = mock_ble_proxy
    matter_client.server_info.ble_proxy_enabled = True

    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    proxy.disconnect.assert_not_awaited()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    proxy.disconnect.assert_awaited_once()
    matter_client.disconnect.assert_awaited()


@pytest.mark.usefixtures("mock_bluetooth_loaded")
async def test_ble_proxy_disconnect_failure_does_not_break_hass_stop(
    hass: HomeAssistant,
    matter_client: MagicMock,
    mock_ble_proxy: tuple[MagicMock, MagicMock],
) -> None:
    """A BLE proxy disconnect failure must not prevent matter_client.disconnect()."""
    proxy, _factory = mock_ble_proxy
    matter_client.server_info.ble_proxy_enabled = True
    proxy.disconnect.side_effect = RuntimeError("boom")

    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    proxy.disconnect.assert_awaited_once()
    matter_client.disconnect.assert_awaited()


async def test_ble_proxy_skipped_when_disabled(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """BLE proxy is not constructed when ble_proxy_enabled is False/missing.

    With ble_proxy_enabled False the lazy `from .ble_proxy import ...` is never
    executed, so we only assert the runtime_data side-effect, not the import.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.ble_proxy is None


@pytest.mark.parametrize(
    "connect_error",
    [ConnectionError("boom"), OSError("boom"), RuntimeError("boom")],
)
@pytest.mark.usefixtures("mock_bluetooth_loaded")
async def test_ble_proxy_connect_failure_does_not_block_setup(
    hass: HomeAssistant,
    matter_client: MagicMock,
    mock_ble_proxy: tuple[MagicMock, MagicMock],
    connect_error: Exception,
) -> None:
    """Setup succeeds with ble_proxy=None when the proxy connect raises."""
    proxy, _factory = mock_ble_proxy
    matter_client.server_info.ble_proxy_enabled = True
    proxy.connect.side_effect = connect_error

    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.ble_proxy is None
    proxy.disconnect.assert_not_awaited()


@pytest.mark.usefixtures("ble_proxy_connect_timeout", "mock_bluetooth_loaded")
async def test_ble_proxy_connect_timeout_does_not_block_setup(
    hass: HomeAssistant,
    matter_client: MagicMock,
    mock_ble_proxy: tuple[MagicMock, MagicMock],
) -> None:
    """Setup succeeds with ble_proxy=None when proxy connect times out."""
    proxy, _factory = mock_ble_proxy
    matter_client.server_info.ble_proxy_enabled = True

    async def hang() -> None:
        await asyncio.Event().wait()

    proxy.connect.side_effect = hang

    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.ble_proxy is None


async def test_ble_proxy_skipped_when_bluetooth_not_loaded(
    hass: HomeAssistant,
    matter_client: MagicMock,
    mock_ble_proxy: tuple[MagicMock, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """BLE proxy is skipped (with a warning) when the bluetooth integration is not loaded."""
    proxy, factory = mock_ble_proxy
    matter_client.server_info.ble_proxy_enabled = True

    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    factory.assert_not_called()
    proxy.connect.assert_not_awaited()
    assert entry.runtime_data.ble_proxy is None
    assert "bluetooth integration is not loaded" in caplog.text


@pytest.mark.usefixtures("mock_bluetooth_loaded")
async def test_ble_proxy_skipped_when_url_underivable(
    hass: HomeAssistant,
    matter_client: MagicMock,
    mock_ble_proxy: tuple[MagicMock, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """BLE proxy is skipped (with a warning) when the WS URL has a non-`/ws` path."""
    proxy, factory = mock_ble_proxy
    matter_client.server_info.ble_proxy_enabled = True

    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/api"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    factory.assert_not_called()
    proxy.connect.assert_not_awaited()
    assert entry.runtime_data.ble_proxy is None
    assert "BLE proxy will not be used" in caplog.text
