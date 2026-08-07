"""Setup / unload / migration tests for the Habitron integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from habitron_client import HabitronError, HabitronTimeoutError
import pytest

from homeassistant.components.habitron import (
    _async_adopt_hub_identity,
    _async_cleanup_stale_devices,
    async_remove_config_entry_device,
)
from homeassistant.components.habitron.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import MOCK_HOST, MOCK_NAME, MOCK_UDN, MOCK_UID

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """A successful setup loads the entry."""
    entry = setup_integration
    assert entry.state is ConfigEntryState.LOADED
    # runtime_data is populated with the coordinator instance
    assert entry.runtime_data is not None


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


async def test_setup_entry_timeout_marks_retry(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
) -> None:
    """A timeout during setup surfaces as SETUP_RETRY, not SETUP_ERROR."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.habitron.smart_hub.SmartHub.async_setup",
        side_effect=TimeoutError("hub silent"),
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
    smhub = entry.runtime_data.smart_hub
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


async def test_setup_entry_connection_refused_marks_retry(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
) -> None:
    """A ``ConnectionRefusedError`` during setup surfaces as SETUP_RETRY."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.habitron.smart_hub.SmartHub.async_setup",
        side_effect=ConnectionRefusedError("hub refused"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_oserror_marks_retry(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
) -> None:
    """A network-level ``OSError`` during setup surfaces as SETUP_RETRY."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.habitron.smart_hub.SmartHub.async_setup",
        side_effect=OSError("network down"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_habitron_error_marks_retry(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
) -> None:
    """A library ``HabitronError`` during setup surfaces as SETUP_RETRY.

    The library raises its own error hierarchy (protocol/connection errors)
    rather than ``OSError`` for a flaky or rebooting hub, so setup must treat it
    as transient and retry instead of failing permanently.
    """
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.habitron.smart_hub.SmartHub.async_setup",
        side_effect=HabitronError("protocol glitch"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


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
async def test_setup_entry_post_refresh_errors_mark_retry(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
    side_effect: Exception,
) -> None:
    """Connection errors raised after the first refresh surface as SETUP_RETRY.

    The first refresh succeeds (stubbed); an error raised by the stale-device
    cleanup that follows exercises ``async_setup_entry``'s own except handlers,
    which translate each error class into ``ConfigEntryNotReady``.
    """
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.habitron._async_cleanup_stale_devices",
        side_effect=side_effect,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_removes_stale_device(
    hass: HomeAssistant,
    setup_homeassistant: None,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
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


async def test_migrate_v1_entry_renames_host_and_drops_the_token(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """A v1 entry keeps working: the host is renamed, the token dropped.

    Entries created before this integration moved to core carry the
    integration-specific ``habitron_host`` key and a websocket token that
    nothing consumes any more; re-adding the hub by hand must not be needed.
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

    assert entry.version == 2
    assert entry.data == {CONF_HOST: MOCK_HOST}
    assert entry.state is ConfigEntryState.LOADED


async def test_migrate_v1_entry_without_the_old_key_is_a_no_op(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
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

    assert entry.version == 2
    assert entry.data == {CONF_HOST: MOCK_HOST}


@pytest.mark.parametrize(
    ("stored_id", "has_mac", "expected"),
    [
        # A host-based fallback from a flow that could not reach the hub.
        ("habitron_192.168.1.50", True, MOCK_UID),
        # A serial, as the custom integration falls back to.
        ("HBT-123456", True, MOCK_UID),
        # Already the identity: nothing to do.
        (MOCK_UID, True, MOCK_UID),
        # No MAC read at all: there is no identity to adopt.
        ("habitron_192.168.1.50", False, "habitron_192.168.1.50"),
    ],
)
async def test_setup_adopts_the_hub_identity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    stored_id: str,
    has_mac: bool,
    expected: str,
) -> None:
    """A successful setup moves the entry onto the hub's MAC.

    Every path derives that MAC, so once the entry carries it the plain
    unique-id check recognises the hub at any address -- no extra matcher.

    Driven directly: the config-entry fixtures stub the first refresh, and
    ``SmartHub.async_setup`` -- which reads the MAC -- runs inside it.
    """
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=stored_id)

    smhub = MagicMock()
    smhub.uid = MOCK_UID
    smhub.has_mac_uid = has_mac

    _async_adopt_hub_identity(hass, mock_config_entry, smhub)

    assert mock_config_entry.unique_id == expected


async def test_setup_does_not_adopt_an_id_another_entry_owns(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A hub configured twice keeps the two entries apart.

    Home Assistant reindexes onto an id already in use and only logs the
    collision, so rewriting here would leave two entries sharing one unique id
    -- and tell the user to file a bug report about it.
    """
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id="habitron_192.168.1.50"
    )
    MockConfigEntry(domain=DOMAIN, title="Other", unique_id=MOCK_UID).add_to_hass(hass)

    smhub = MagicMock()
    smhub.uid = MOCK_UID
    smhub.has_mac_uid = True

    _async_adopt_hub_identity(hass, mock_config_entry, smhub)

    assert mock_config_entry.unique_id == "habitron_192.168.1.50"


async def test_setup_adopts_before_the_update_listener_exists(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
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

    with (
        patch.object(
            type(hass.config_entries),
            "async_reload",
            new=AsyncMock(return_value=True),
        ) as reload,
        patch(
            "homeassistant.components.habitron._async_adopt_hub_identity",
            side_effect=lambda hass, entry, smhub: (
                hass.config_entries.async_update_entry(entry, unique_id=MOCK_UID)
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.unique_id == MOCK_UID
    reload.assert_not_called()


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
