"""Tests for the Elke27 integration setup."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from elke27_lib import LinkKeys, PanelInfo, PanelSnapshot, TableInfo
from elke27_lib.errors import Elke27LinkRequiredError, Elke27TimeoutError
import pytest

from homeassistant.components.elke27 import (
    _async_disconnect_failed_setup,
    async_unload_entry,
)
from homeassistant.components.elke27.const import (
    CONF_LINK_KEYS_JSON,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.components.elke27.models import Elke27RuntimeData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_CLIENT_ID, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


def _snapshot() -> PanelSnapshot:
    """Return a minimal panel snapshot."""
    return PanelSnapshot(
        panel=PanelInfo(serial="1234", model="E27", firmware="1.0"),
        table_info=TableInfo(),
        areas={},
        zones={},
        zone_definitions={},
        outputs={},
        output_definitions={},
        lights={},
        barriers={},
        locks={},
        thermostats={},
        version=1,
        updated_at=dt_util.utcnow(),
    )


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
        async_config_entry_first_refresh=AsyncMock(return_value=None),
        async_stop=AsyncMock(return_value=None),
        data=_snapshot(),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_CLIENT_ID: "112233445566",
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
        coordinator.async_config_entry_first_refresh.assert_awaited_once()
        assert isinstance(entry.runtime_data, Elke27RuntimeData)
        assert (
            dr.async_get(hass).async_get_device({(DOMAIN, "112233445566")}) is not None
        )

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    coordinator.async_stop.assert_awaited_once()
    hub.async_disconnect.assert_awaited_once()


async def test_setup_forward_entry_setups_error_cleans_up(
    hass: HomeAssistant,
) -> None:
    """Test platform forwarding errors clean up setup resources."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(return_value=None),
        async_disconnect=AsyncMock(return_value=None),
    )
    coordinator = SimpleNamespace(
        async_start=AsyncMock(return_value=None),
        async_config_entry_first_refresh=AsyncMock(return_value=None),
        async_stop=AsyncMock(return_value=None),
        data=_snapshot(),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.18",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_CLIENT_ID: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch(
            "homeassistant.components.elke27.Elke27DataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(side_effect=ConfigEntryError),
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    coordinator.async_stop.assert_awaited_once()
    hub.async_disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(Elke27TimeoutError(), id="library-timeout"),
        pytest.param(OSError("connection refused"), id="os-error"),
    ],
)
async def test_setup_transient_error_returns_not_ready(
    hass: HomeAssistant, error: Exception
) -> None:
    """Test transient setup errors return not ready."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(side_effect=error),
        async_disconnect=AsyncMock(return_value=None),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.12",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_CLIENT_ID: "112233445566",
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


async def test_setup_transient_error_suppresses_disconnect_error(
    hass: HomeAssistant,
) -> None:
    """Test connection cleanup errors do not mask transient setup errors."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(side_effect=Elke27TimeoutError()),
        async_disconnect=AsyncMock(side_effect=RuntimeError("disconnect failed")),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.12",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_CLIENT_ID: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch(
            "homeassistant.components.elke27.Elke27DataUpdateCoordinator"
        ) as coordinator_cls,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator_cls.assert_not_called()
    hub.async_disconnect.assert_awaited_once()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_disconnect_failed_setup_preserves_cancelled_error() -> None:
    """Test setup cleanup preserves cancellation."""
    hub = SimpleNamespace(
        async_disconnect=AsyncMock(side_effect=asyncio.CancelledError),
    )

    with pytest.raises(asyncio.CancelledError):
        await _async_disconnect_failed_setup(hub)

    hub.async_disconnect.assert_awaited_once()


async def test_setup_initial_refresh_error_cleans_up_and_returns_not_ready(
    hass: HomeAssistant,
) -> None:
    """Test initial refresh errors clean up setup resources."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(return_value=None),
        async_disconnect=AsyncMock(return_value=None),
    )
    coordinator = SimpleNamespace(
        async_start=AsyncMock(return_value=None),
        async_config_entry_first_refresh=AsyncMock(side_effect=ConfigEntryNotReady),
        async_stop=AsyncMock(return_value=None),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.13",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_CLIENT_ID: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch(
            "homeassistant.components.elke27.Elke27DataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ) as forward_entry_setups,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hub.async_connect.assert_awaited_once()
    coordinator.async_start.assert_awaited_once()
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    coordinator.async_stop.assert_awaited_once()
    hub.async_disconnect.assert_awaited_once()
    forward_entry_setups.assert_not_called()


async def test_setup_initial_refresh_config_entry_error_fails_setup(
    hass: HomeAssistant,
) -> None:
    """Test config entry refresh errors clean up and fail setup."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(return_value=None),
        async_disconnect=AsyncMock(return_value=None),
    )
    coordinator = SimpleNamespace(
        async_start=AsyncMock(return_value=None),
        async_config_entry_first_refresh=AsyncMock(side_effect=ConfigEntryError),
        async_stop=AsyncMock(return_value=None),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.13",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_CLIENT_ID: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch(
            "homeassistant.components.elke27.Elke27DataUpdateCoordinator",
            return_value=coordinator,
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    coordinator.async_start.assert_awaited_once()
    coordinator.async_stop.assert_awaited_once()
    hub.async_disconnect.assert_awaited_once()


async def test_setup_start_error_cleans_up(
    hass: HomeAssistant,
) -> None:
    """Test coordinator start errors clean up setup resources."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(return_value=None),
        async_disconnect=AsyncMock(return_value=None),
    )
    coordinator = SimpleNamespace(
        async_start=AsyncMock(side_effect=ConfigEntryError),
        async_config_entry_first_refresh=AsyncMock(return_value=None),
        async_stop=AsyncMock(return_value=None),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.13",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_CLIENT_ID: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch(
            "homeassistant.components.elke27.Elke27DataUpdateCoordinator",
            return_value=coordinator,
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator.async_start.assert_awaited_once()
    coordinator.async_config_entry_first_refresh.assert_not_awaited()
    coordinator.async_stop.assert_awaited_once()
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


async def test_unload_suppresses_cleanup_errors(hass: HomeAssistant) -> None:
    """Test unload suppresses cleanup errors after platforms unload."""
    hub = SimpleNamespace(
        async_disconnect=AsyncMock(side_effect=RuntimeError("disconnect failed")),
    )
    coordinator = SimpleNamespace(
        async_stop=AsyncMock(side_effect=RuntimeError("stop failed")),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.17"},
    )
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=True),
    ):
        assert await async_unload_entry(hass, entry)

    coordinator.async_stop.assert_awaited_once()
    hub.async_disconnect.assert_awaited_once()


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
            CONF_CLIENT_ID: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch("homeassistant.components.elke27.Elke27DataUpdateCoordinator"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_uses_client_id(hass: HomeAssistant) -> None:
    """Verify setup passes the stored client ID to the hub."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(return_value=None),
        async_disconnect=AsyncMock(return_value=None),
    )
    coordinator = SimpleNamespace(
        async_start=AsyncMock(return_value=None),
        async_config_entry_first_refresh=AsyncMock(return_value=None),
        async_stop=AsyncMock(return_value=None),
        data=_snapshot(),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.15",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_CLIENT_ID: "entryclientid",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub) as hub_cls,
        patch(
            "homeassistant.components.elke27.Elke27DataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hub_cls.assert_called_once_with(
        hass,
        "192.168.1.15",
        DEFAULT_PORT,
        LinkKeys("tk", "lk", "lh").to_json(),
        "entryclientid",
        None,
    )
