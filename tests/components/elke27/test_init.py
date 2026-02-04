"""Tests for the Elke27 integration setup."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from elke27_lib import LinkKeys
from elke27_lib.errors import Elke27LinkRequiredError, Elke27TimeoutError

import pytest
from homeassistant.components.elke27 import (
    _async_migrate_unique_ids,
    _panel_name_from_entry,
)
from homeassistant.components.elke27.const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS_JSON,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.components.elke27.models import Elke27RuntimeData
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
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

    with patch(
        "homeassistant.components.elke27.Elke27Hub", return_value=hub
    ), patch(
        "homeassistant.components.elke27.Elke27DataUpdateCoordinator",
        return_value=coordinator,
    ), patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        _async_forward_entry_setups,
    ), patch.object(
        hass.config_entries,
        "async_unload_platforms",
        _async_unload_platforms,
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

    with patch(
        "homeassistant.components.elke27.Elke27Hub", return_value=hub
    ), patch(
        "homeassistant.components.elke27.Elke27DataUpdateCoordinator"
    ) as coordinator_cls, patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        _async_forward_entry_setups,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator_cls.assert_not_called()
    hub.async_disconnect.assert_awaited_once()


async def test_setup_missing_link_keys_raises_auth_failed(
    hass: HomeAssistant,
) -> None:
    """Test setup fails when link keys are missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.13", CONF_PORT: DEFAULT_PORT},
    )
    entry.add_to_hass(hass)

    with pytest.raises(ConfigEntryAuthFailed):
        await hass.config_entries.async_setup(entry.entry_id)


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

    with patch(
        "homeassistant.components.elke27.Elke27Hub", return_value=hub
    ), patch(
        "homeassistant.components.elke27.Elke27DataUpdateCoordinator"
    ):
        with pytest.raises(ConfigEntryAuthFailed):
            await hass.config_entries.async_setup(entry.entry_id)


def test_panel_name_from_entry() -> None:
    """Verify panel name extraction from entry data."""
    assert _panel_name_from_entry({"panel_name": "Panel"}) == "Panel"
    assert _panel_name_from_entry({"name": "Panel 2"}) == "Panel 2"
    assert _panel_name_from_entry(None) is None


async def test_migrate_unique_ids(hass: HomeAssistant) -> None:
    """Verify unique IDs are migrated to the new format."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.10"},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    base = "aa:bb:cc:dd:ee:ff"
    old_unique_id = f"{base}_sensor_1"
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        old_unique_id,
        config_entry=entry,
    )

    await _async_migrate_unique_ids(hass, entry, base)

    entry_id = registry.async_get_entity_id("sensor", DOMAIN, f"{base}:sensor:1")
    assert entry_id is not None
