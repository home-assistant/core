"""Setup / unload / migration tests for the Habitron integration."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from habitron_client import HabitronError, HabitronTimeoutError, SmartHub
import pytest

from homeassistant.components.habitron import (
    _async_cleanup_stale_devices,
    async_remove_config_entry_device,
)
from homeassistant.components.habitron.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.habitron.coordinator import HbtnCoordinator
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_SSDP, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.service_info.ssdp import ATTR_UPNP_UDN, SsdpServiceInfo
from homeassistant.setup import async_setup_component

from .const import MOCK_HOST, MOCK_MAC, MOCK_NAME, MOCK_UDN, MOCK_UID

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    setup_integration: MockConfigEntry,
) -> None:
    """A successful setup loads the entry and initialises the hub model.

    The first refresh runs the coordinator setup, so the hub is identified and
    its device registered before the first poll.
    """
    entry = setup_integration
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.uid == MOCK_UID
    assert entry.unique_id == MOCK_UID
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_UID), entry.entry_id
    )


async def test_unload_entry(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """Unloading the last entry tears down state."""
    entry = setup_integration
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_update_listener_triggers_reload(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """Updating entry options triggers an entry reload."""
    entry = setup_integration
    with patch.object(
        hass.config_entries, "async_reload", new=AsyncMock(return_value=True)
    ) as mock_reload:
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_HOST: "192.168.1.99"},
        )
        await hass.async_block_till_done()
        mock_reload.assert_called_with(entry.entry_id)


async def test_failed_setup_still_releases_the_client(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
) -> None:
    """A setup that fails still closes the client and clears the router issue.

    Home Assistant runs the on-unload callbacks for a failed setup but never
    calls ``async_unload_entry``, so cleanup registered only there would leak
    the client and leave the repair issue standing across every retry.
    """
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.habitron.coordinator."
            "HbtnCoordinator._async_connect_and_build",
            side_effect=HabitronError("protocol glitch"),
        ),
        patch(
            "homeassistant.components.habitron.coordinator.HbtnCoordinator.async_close"
        ) as mock_close,
        patch(
            "homeassistant.components.habitron.coordinator."
            "HbtnCoordinator.async_clear_router_issue"
        ) as mock_clear,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_close.assert_called_once()
    mock_clear.assert_called_once()


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(TimeoutError("hub silent"), id="timeout"),
        pytest.param(HabitronTimeoutError("hub silent"), id="library_timeout"),
        pytest.param(ConnectionRefusedError("hub refused"), id="refused"),
        pytest.param(OSError("network down"), id="oserror"),
        pytest.param(HabitronError("protocol glitch"), id="habitron_error"),
    ],
)
async def test_setup_entry_build_errors_mark_retry(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
    side_effect: Exception,
) -> None:
    """A failure while connecting and building the model surfaces as SETUP_RETRY.

    The library raises its own error hierarchy (protocol and connection errors)
    rather than ``OSError`` for a flaky or rebooting hub, so setup has to treat
    each of these as transient and retry instead of failing permanently.
    """
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.habitron.coordinator."
        "HbtnCoordinator._async_connect_and_build",
        side_effect=side_effect,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_remove_config_entry_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    setup_integration: MockConfigEntry,
) -> None:
    """Only devices whose Habitron member is gone from the bus may be removed."""

    entry = setup_integration
    smhub = entry.runtime_data
    # Populate the model with a router uid and a live module so their devices
    # are treated as present.
    smhub.router.uid = "router-uid"
    smhub.router.modules = [MagicMock(uid="module-uid")]

    # Hub, router and a still-present module all identify live devices → NOT
    # removable.
    for present_uid in (smhub.uid, "router-uid", "module-uid"):
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, present_uid)},
            name=f"Device {present_uid}",
        )
        assert await async_remove_config_entry_device(hass, entry, device) is False, (
            f"Expected {present_uid!r} to be non-removable"
        )

    # A uid no longer on the bus (a removed module) → removable.
    other_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "some-other-uid")},
        name="Sub module",
    )
    assert await async_remove_config_entry_device(hass, entry, other_device) is True


async def test_remove_device_is_refused_while_the_entry_is_not_loaded(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    setup_integration: MockConfigEntry,
) -> None:
    """Without a loaded entry there is no bus model to check the device against.

    Core drops ``runtime_data`` on unload, but the device page still offers the
    removal.
    """
    entry = setup_integration
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "gone-module-uid")},
    )

    assert await async_remove_config_entry_device(hass, entry, device) is False


async def test_unload_entry_returns_false_when_platform_unload_fails(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """A failing platform-unload propagates as False without touching state."""

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        return_value=False,
    ):
        ok = await hass.config_entries.async_unload(setup_integration.entry_id)
    assert ok is False


@pytest.mark.parametrize(
    "side_effect",
    [
        TimeoutError("silent"),
        HabitronTimeoutError("silent"),
        ConnectionRefusedError("refused"),
        OSError("network down"),
        HabitronError("protocol glitch"),
    ],
)
async def test_setup_entry_post_refresh_errors_are_not_masked(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
    side_effect: Exception,
) -> None:
    """An error after the first refresh is a defect, not a reason to retry.

    The connection handlers cover the first refresh only. Everything after it
    is local bookkeeping, so a failure there must surface as a setup error
    instead of disappearing into an indefinite retry loop.
    """
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.habitron._async_cleanup_stale_devices",
        side_effect=side_effect,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_removes_stale_device(
    hass: HomeAssistant,
    setup_homeassistant: None,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """``_async_cleanup_stale_devices`` removes registry entries for gone modules."""

    mock_config_entry.add_to_hass(hass)
    stale = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "stale-uid")},
        name="Gone module",
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get(stale.id) is None


async def test_migrate_v1_entry_renames_the_host(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """A v1 entry keeps working: the host key is renamed in place.

    Entries created before this integration moved to core carry the
    integration-specific ``habitron_host`` key; re-adding the hub by hand must
    not be needed. The websocket token stays -- the custom integration reads it
    from this same entry.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UDN,
        version=1,
        data={"habitron_host": MOCK_HOST, "websock_token": "rotated-token"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (entry.version, entry.minor_version) == (2, 2)
    assert entry.data == {CONF_HOST: MOCK_HOST, "websock_token": "rotated-token"}
    assert entry.state is ConfigEntryState.LOADED


async def test_migrate_v1_entry_without_the_old_key_is_a_no_op(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """A v1 entry that already uses the shared key is only version-bumped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UDN,
        version=1,
        data={CONF_HOST: MOCK_HOST},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (entry.version, entry.minor_version) == (2, 2)
    assert entry.data == {CONF_HOST: MOCK_HOST}


async def _connect_and_build(coordinator: HbtnCoordinator) -> None:
    """Build a hub reporting its MAC, as the real build would."""
    coordinator._client = AsyncMock()
    coordinator.host = MOCK_HOST
    coordinator.hub = SmartHub(uid=MOCK_UID, lan_mac=MOCK_MAC, macs=[MOCK_MAC])
    await coordinator._async_resolve_uid()
    # The real build polls the bus here, letting a concurrent setup run.
    await asyncio.sleep(0)
    await asyncio.sleep(0)


@pytest.fixture
def mock_bus() -> Generator[None]:
    """Run the coordinator's real setup and polls over a stubbed bus."""
    with (
        patch(
            "homeassistant.components.habitron.coordinator."
            "HbtnCoordinator._async_connect_and_build",
            new=_connect_and_build,
        ),
        patch(
            "homeassistant.components.habitron.coordinator.async_refresh_system",
            new=AsyncMock(return_value=4711),
        ),
        patch(
            "homeassistant.components.habitron.coordinator.async_refresh_hub",
            new=AsyncMock(),
        ),
    ):
        yield


@pytest.mark.usefixtures("setup_homeassistant", "mock_habitron_client", "mock_bus")
async def test_setup_adopts_before_the_update_listener_exists(
    hass: HomeAssistant,
) -> None:
    """Rewriting the entry must not reload the entry that is still setting up.

    ``async_update_entry`` fires the update listeners, and ours reloads
    unconditionally -- so the identity has to be adopted before that listener
    is registered.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="habitron_192.168.1.50",
        version=2,
        data={CONF_HOST: MOCK_HOST},
    )
    entry.add_to_hass(hass)

    with patch.object(
        type(hass.config_entries),
        "async_reload",
        new=AsyncMock(return_value=True),
    ) as reload:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.unique_id == MOCK_UID
    reload.assert_not_called()


@pytest.mark.usefixtures("setup_homeassistant", "mock_habitron_client", "mock_bus")
async def test_concurrent_legacy_entries_of_one_hub_load_only_once(
    hass: HomeAssistant,
) -> None:
    """Two carried-over entries for the same hub cannot both claim its MAC.

    The custom integration keys a hub without a usable MAC by its serial or its
    host, so one hub can arrive as two entries. Set up concurrently, both read
    the same MAC; the second must find it taken even though the build still
    yields to the event loop after the identity check.
    """
    entries = [
        MockConfigEntry(
            domain=DOMAIN,
            title=MOCK_NAME,
            unique_id=unique_id,
            version=2,
            minor_version=2,
            data={CONF_HOST: MOCK_HOST},
        )
        for unique_id in ("HBT-123456", "habitron_192.168.1.50")
    ]
    for entry in entries:
        entry.add_to_hass(hass)

    # Loading the integration sets up all its entries concurrently.
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert [entry.state for entry in entries] == [
        ConfigEntryState.LOADED,
        ConfigEntryState.SETUP_ERROR,
    ]
    assert [entry.unique_id for entry in entries] == [MOCK_UID, "habitron_192.168.1.50"]


async def test_cleanup_keeps_a_device_with_one_live_identifier(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A device is stale only when *none* of its Habitron uids is on the bus.

    Device entries can carry several identifiers; removing on the first stale
    one would delete a device that is still live under another -- the opposite
    of what ``async_remove_config_entry_device`` allows.

    Driven directly: the config-entry fixtures stub the first refresh, and
    ``SmartHub.async_setup`` runs inside it, so the uids never reach the
    registry through that path.
    """
    mock_config_entry.add_to_hass(hass)
    survivor = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "gone-uid"), (DOMAIN, "module-uid")},
        name="Module, re-identified",
    )
    stale = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "gone-uid-2")},
        name="Gone module",
    )

    smhub = MagicMock()
    smhub.uid = "hub-uid"
    smhub.router.uid = "router-uid"
    smhub.router.modules = [MagicMock(uid="module-uid")]

    _async_cleanup_stale_devices(hass, mock_config_entry, smhub)

    assert device_registry.async_get(survivor.id) is not None
    assert device_registry.async_get(stale.id) is None


async def test_migrate_v2_entry_is_bumped_and_keeps_the_token(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """A v2 entry from the custom integration is bumped, not stripped.

    The bump is minor on purpose: raising the major version would make Home
    Assistant refuse this entry if the user ever went back to the custom
    integration, which numbers its entries 2. The websocket token is kept for
    the same reason -- that integration reads it from this very entry, with a
    plain subscript, so dropping it would break the fallback outright.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UID,
        version=2,
        data={CONF_HOST: MOCK_HOST, "websock_token": "rotated-token"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (entry.version, entry.minor_version) == (2, 2)
    assert entry.data == {CONF_HOST: MOCK_HOST, "websock_token": "rotated-token"}
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("setup_homeassistant", "mock_habitron_client", "mock_bus")
async def test_rediscovery_after_migration_updates_the_live_entry(
    hass: HomeAssistant,
) -> None:
    """A migrated hub that moves is followed by its live entry, not an ignored one.

    The hub was ignored once and then carried over from the custom integration
    under a serial. Setup moves the live entry onto the MAC and drops the
    ignored entry, so a later discovery at a new address finds the live one.
    """
    MockConfigEntry(
        domain=DOMAIN, unique_id=MOCK_UID, source=SOURCE_IGNORE
    ).add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="HBT-123456",
        version=2,
        minor_version=2,
        data={CONF_HOST: MOCK_HOST},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.config_entries.async_entries(DOMAIN) == [entry]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
            ssdp_st="urn:habitron-com:device:SmartHub:1",
            ssdp_location="http://192.168.1.77:80/desc.xml",
            upnp={ATTR_UPNP_UDN: MOCK_UDN},
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == MOCK_UID
    assert entry.data[CONF_HOST] == "192.168.1.77"


@pytest.mark.usefixtures("setup_homeassistant", "mock_habitron_client", "mock_bus")
async def test_router_issue_clears_without_any_sensor_entity(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The polls go on without entities, so a router issue clears by itself.

    A hub and router without members give the sensor platform nothing to add,
    and the coordinator only polls while something listens to it.
    """
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    router = mock_config_entry.runtime_data.router
    issue_id = f"router_system_error_{router.uid}"

    for sys_ok, raised in ((False, True), (True, False)):
        router.sys_ok = sys_ok
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert (issue_registry.async_get_issue(DOMAIN, issue_id) is not None) is raised
