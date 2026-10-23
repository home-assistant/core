"""Test the KNX backup platform."""

import asyncio
from unittest.mock import AsyncMock, patch

from knx_telegram_store import KnxTelegramStoreException, TelegramQuery
import pytest

from homeassistant.components.backup import DATA_MANAGER
from homeassistant.components.knx.backup import async_post_backup, async_pre_backup
from homeassistant.components.knx.const import (
    CONF_KNX_TELEGRAM_DB_BACKEND,
    CONF_KNX_TELEGRAM_DB_POSTGRES_DSN,
    KNX_MODULE_KEY,
    KNX_TELEGRAM_BACKEND_POSTGRES,
)
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit

from tests.components.backup.common import setup_backup_integration


async def test_backup_platform_is_registered(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test the backup integration picks up the KNX backup platform."""
    await knx.setup_integration()
    await setup_backup_integration(hass)

    assert "knx" in hass.data[DATA_MANAGER].platforms


async def _stored_count(hass: HomeAssistant) -> int:
    store = hass.data[KNX_MODULE_KEY].telegrams.store
    assert store is not None
    result = await store.query(TelegramQuery())
    return len(result.telegrams)


async def test_backup_holds_writes_until_post_backup(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test pre-backup flushes and then keeps telegrams in the buffer until post-backup."""
    await knx.setup_integration(real_telegram_store=True)
    store = hass.data[KNX_MODULE_KEY].telegrams.store
    assert store is not None

    await knx.receive_write("1/3/4", True)
    await hass.async_block_till_done()
    assert await _stored_count(hass) == 0

    await async_pre_backup(hass)
    assert await _stored_count(hass) == 1

    await knx.receive_write("1/3/4", False)
    await hass.async_block_till_done()
    await store.flush()
    assert await _stored_count(hass) == 1

    await async_post_backup(hass)
    await store.flush()
    assert await _stored_count(hass) == 2


async def test_pre_backup_store_error_is_logged(
    hass: HomeAssistant, knx: KNXTestKit, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a store that cannot be locked does not abort the backup."""
    await knx.setup_integration()
    store = hass.data[KNX_MODULE_KEY].telegrams.store
    assert store is not None

    with patch.object(
        store, "begin_backup", AsyncMock(side_effect=KnxTelegramStoreException("busy"))
    ):
        await async_pre_backup(hass)
    assert "Could not prepare the KNX telegram database" in caplog.text

    await async_post_backup(hass)


async def test_pre_backup_timeout_is_logged(
    hass: HomeAssistant, knx: KNXTestKit, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a lock that cannot be taken in time does not abort the backup."""
    await knx.setup_integration()
    store = hass.data[KNX_MODULE_KEY].telegrams.store
    assert store is not None

    async def _never() -> None:
        await asyncio.Event().wait()

    with (
        patch.object(store, "begin_backup", _never),
        patch("homeassistant.components.knx.backup.LOCK_TIMEOUT", 0),
    ):
        await async_pre_backup(hass)
    assert "Could not prepare the KNX telegram database" in caplog.text


async def test_backup_is_noop_for_postgres_backend(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test a PostgreSQL store is left alone, its data is not part of the backup."""
    knx.mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        knx.mock_config_entry,
        options=knx.mock_config_entry.options
        | {
            CONF_KNX_TELEGRAM_DB_BACKEND: KNX_TELEGRAM_BACKEND_POSTGRES,
            CONF_KNX_TELEGRAM_DB_POSTGRES_DSN: "postgresql://user:secret@db.local/knx",
        },
    )
    mock_store = AsyncMock()
    mock_store.needs_migration.return_value = False
    with patch(
        "homeassistant.components.knx.telegrams.BufferedPostgresStore",
        return_value=mock_store,
    ):
        await knx.setup_integration(add_entry_to_hass=False, real_telegram_store=True)

    await async_pre_backup(hass)
    await async_post_backup(hass)

    mock_store.begin_backup.assert_not_called()
    mock_store.end_backup.assert_not_called()


async def test_backup_is_noop_without_knx(hass: HomeAssistant) -> None:
    """Test the hooks do nothing when KNX is not set up."""
    await async_pre_backup(hass)
    await async_post_backup(hass)
