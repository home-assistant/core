"""Tests for the Elke27 integration setup."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from elke27_lib import LinkKeys
from elke27_lib.errors import Elke27LinkRequiredError, Elke27TimeoutError

from homeassistant.components.elke27 import (
    _async_migrate_unique_ids,
    async_unload_entry,
)
from homeassistant.components.elke27.const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LEGACY_PIN,
    CONF_LINK_KEYS_JSON,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.components.elke27.models import Elke27RuntimeData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_setup_unload_calls_connect_disconnect_and_subscribe(
    hass: HomeAssistant,
) -> None:
    """Test setup/unload uses hub and coordinator lifecycle."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(return_value=None),
        async_disconnect=AsyncMock(return_value=None),
    )

    coordinator = SimpleNamespace(
        async_start=AsyncMock(return_value=None),
        async_refresh_now=AsyncMock(return_value=None),
        async_stop=AsyncMock(return_value=None),
        data=None,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_INTEGRATION_SERIAL: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    async def _async_forward_entry_setups(*_args, **_kwargs) -> bool:
        return True

    async def _async_unload_platforms(*_args, **_kwargs) -> bool:
        return True

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch(
            "homeassistant.components.elke27.Elke27DataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            _async_forward_entry_setups,
        ),
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            _async_unload_platforms,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        hub.async_connect.assert_awaited_once()
        coordinator.async_start.assert_awaited_once()
        coordinator.async_refresh_now.assert_awaited_once()
        assert isinstance(entry.runtime_data, Elke27RuntimeData)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    coordinator.async_stop.assert_awaited_once()
    hub.async_disconnect.assert_awaited_once()


async def test_setup_transient_error_returns_not_ready(
    hass: HomeAssistant,
) -> None:
    """Test transient setup errors return not ready."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(side_effect=Elke27TimeoutError()),
        async_disconnect=AsyncMock(return_value=None),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.12",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_INTEGRATION_SERIAL: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    async def _async_forward_entry_setups(*_args, **_kwargs) -> bool:
        return True

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch(
            "homeassistant.components.elke27.Elke27DataUpdateCoordinator"
        ) as coordinator_cls,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            _async_forward_entry_setups,
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator_cls.assert_not_called()
    hub.async_disconnect.assert_awaited_once()


async def test_unload_keeps_runtime_when_platform_unload_fails(
    hass: HomeAssistant,
) -> None:
    """Test unload leaves runtime running when platform unload fails."""
    hub = SimpleNamespace(
        async_disconnect=AsyncMock(return_value=None),
    )
    coordinator = SimpleNamespace(
        async_stop=AsyncMock(return_value=None),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.16"},
    )
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=False),
    ):
        assert not await async_unload_entry(hass, entry)

    coordinator.async_stop.assert_not_awaited()
    hub.async_disconnect.assert_not_awaited()


async def test_setup_missing_link_keys_raises_auth_failed(
    hass: HomeAssistant,
) -> None:
    """Test setup fails when link keys are missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.13", CONF_PORT: DEFAULT_PORT},
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_link_required_raises_auth_failed(
    hass: HomeAssistant,
) -> None:
    """Test link-required errors raise auth failed."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(side_effect=Elke27LinkRequiredError()),
        async_disconnect=AsyncMock(return_value=None),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.14",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_INTEGRATION_SERIAL: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch("homeassistant.components.elke27.Elke27DataUpdateCoordinator"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_migrate_unique_ids(hass: HomeAssistant) -> None:
    """Verify unique IDs are migrated to the new format."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.10"},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    base = "aa:bb:cc:dd:ee:ff"
    old_unique_id = f"{base}_area_1"
    registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        old_unique_id,
        config_entry=entry,
    )

    await _async_migrate_unique_ids(hass, entry, base)

    entry_id = registry.async_get_entity_id(
        "alarm_control_panel", DOMAIN, f"{base}:area:1"
    )
    assert entry_id is not None


async def test_migrate_unique_ids_skips_without_suffix(hass: HomeAssistant) -> None:
    """Verify migration skips IDs without an underscore suffix."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.24"})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    base = "aa:bb:cc"
    registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        f"{base}_area",
        config_entry=entry,
    )

    await _async_migrate_unique_ids(hass, entry, base)


async def test_migrate_unique_ids_skips_other_entry(hass: HomeAssistant) -> None:
    """Verify migration skips entries from other config entries."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.22"})
    entry.add_to_hass(hass)
    other_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.23"})
    other_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    base = "aa:bb:cc"
    registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        f"{base}_area_1",
        config_entry=other_entry,
    )

    await _async_migrate_unique_ids(hass, entry, base)


async def test_setup_updates_integration_serial_and_pin(hass: HomeAssistant) -> None:
    """Verify integration serial is generated and pin is removed."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(return_value=None),
        async_disconnect=AsyncMock(return_value=None),
    )
    coordinator = SimpleNamespace(
        async_start=AsyncMock(return_value=None),
        async_refresh_now=AsyncMock(return_value=None),
        async_stop=AsyncMock(return_value=None),
        data=None,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.15",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_LEGACY_PIN: "1234",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch(
            "homeassistant.components.elke27.Elke27DataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch(
            "homeassistant.components.elke27.async_get_integration_serial",
            AsyncMock(return_value="998877"),
        ),
        patch.object(hass.config_entries, "async_update_entry") as update_entry,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    update_entry.assert_called()


async def test_setup_removes_pin_when_serial_exists(hass: HomeAssistant) -> None:
    """Verify pin removal updates entry when serial exists."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(return_value=None),
        async_disconnect=AsyncMock(return_value=None),
    )
    coordinator = SimpleNamespace(
        async_start=AsyncMock(return_value=None),
        async_refresh_now=AsyncMock(return_value=None),
        async_stop=AsyncMock(return_value=None),
        data=None,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.16",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_INTEGRATION_SERIAL: "112233445566",
            CONF_LEGACY_PIN: "1234",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch(
            "homeassistant.components.elke27.Elke27DataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch.object(hass.config_entries, "async_update_entry") as update_entry,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    update_entry.assert_called()


async def test_migrate_unique_ids_skips_unmatched(hass: HomeAssistant) -> None:
    """Verify migration skips non-matching entries and collisions."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.20"})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    base = "aa:bb"
    registry.async_get_or_create("alarm_control_panel", DOMAIN, f"{base}_area")
    registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        f"{base}_area_2",
        config_entry=entry,
    )
    registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        f"{base}:area:2",
        config_entry=entry,
    )
    registry.async_get_or_create(
        "alarm_control_panel",
        "other",
        f"{base}_area_3",
        config_entry=entry,
    )
    other_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.21"})
    other_entry.add_to_hass(hass)
    registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        f"{base}_area",
        config_entry=other_entry,
    )

    await _async_migrate_unique_ids(hass, entry, base)
