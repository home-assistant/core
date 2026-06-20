"""Setup / unload / migration tests for the Habitron integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from habitron_client import HabitronError

from homeassistant.components.habitron import async_remove_config_entry_device
from homeassistant.components.habitron.const import DOMAIN
from homeassistant.components.habitron.services import SERVICE_HUB_RESTART
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """A successful setup loads the entry and registers services."""
    entry = setup_integration
    assert entry.state is ConfigEntryState.LOADED
    # runtime_data is populated with the SmartHub instance
    assert entry.runtime_data is not None
    # Services are registered globally on the domain
    assert hass.services.has_service(DOMAIN, SERVICE_HUB_RESTART)


async def test_unload_entry(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """Unloading the last entry tears down state; domain services persist."""
    entry = setup_integration
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    # Services are registered once in async_setup and live for the integration's
    # lifetime (action-setup rule); they are not torn down with the entry.
    assert hass.services.has_service(DOMAIN, SERVICE_HUB_RESTART)


async def test_services_kept_while_other_entry_loaded(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """A second loaded entry keeps services alive when the first unloads."""
    other = MockConfigEntry(
        domain=DOMAIN,
        title="Habitron #2",
        unique_id="hub-2",
        data=setup_integration.data,
        options=setup_integration.options,
    )
    other.add_to_hass(hass)
    assert await hass.config_entries.async_setup(other.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    # Other entry still here → services must still be registered.
    assert hass.services.has_service(DOMAIN, SERVICE_HUB_RESTART)


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
    """A device matching the hub UID cannot be removed standalone."""

    entry = setup_integration
    smhub = entry.runtime_data
    dev_reg = dr.async_get(hass)
    hub_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, smhub.uid)},
        name="Hub",
    )
    # Hub device identifies the smhub itself → must NOT be removable.
    assert await async_remove_config_entry_device(hass, entry, hub_device) is False, (
        f"Expected False; smhub.uid={smhub.uid!r}, identifiers={hub_device.identifiers!r}"
    )

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
