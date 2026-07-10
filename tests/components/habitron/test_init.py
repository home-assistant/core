"""Setup / unload / migration tests for the Habitron integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from habitron_client import HabitronError, HabitronTimeoutError
import pytest

from homeassistant.components.habitron import async_remove_config_entry_device
from homeassistant.components.habitron.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

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
            options={**entry.options, "websock_token": "rotated-token"},
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
    setup_integration: MockConfigEntry,
) -> None:
    """Only devices whose Habitron member is gone from the bus may be removed."""

    entry = setup_integration
    smhub = entry.runtime_data.smart_hub
    # Populate the model with a router uid and a live module so their devices
    # are treated as present.
    smhub.router.uid = "router-uid"
    smhub.router.modules = [MagicMock(uid="module-uid")]
    dev_reg = dr.async_get(hass)

    # Hub, router and a still-present module all identify live devices → NOT
    # removable.
    for present_uid in (smhub.uid, "router-uid", "module-uid"):
        device = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, present_uid)},
            name=f"Device {present_uid}",
        )
        assert await async_remove_config_entry_device(hass, entry, device) is False, (
            f"Expected {present_uid!r} to be non-removable"
        )

    # A uid no longer on the bus (a removed module) → removable.
    other_device = dev_reg.async_get_or_create(
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
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """``_async_cleanup_stale_devices`` removes registry entries for gone modules."""

    mock_config_entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    stale = dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "stale-uid")},
        name="Gone module",
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert dev_reg.async_get(stale.id) is None
