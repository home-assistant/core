"""KNX Telegrams Tests."""

from __future__ import annotations

import asyncio
from copy import copy
from datetime import datetime
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from knx_telegram_store import KnxTelegramStoreException, StoredTelegram, TelegramQuery
import pytest

from homeassistant.components.knx.const import (
    CONF_KNX_TELEGRAM_DB_BACKEND,
    CONF_KNX_TELEGRAM_DB_POSTGRES_DSN,
    CONF_KNX_TELEGRAM_DB_RETENTION_DAYS,
    DOMAIN,
    KNX_MODULE_KEY,
    KNX_TELEGRAM_BACKEND_POSTGRES,
    REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR,
)
from homeassistant.components.knx.telegrams import TelegramDict
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .conftest import KNXTestKit

from tests.common import async_fire_time_changed, async_load_json_object_fixture

MOCK_TIMESTAMP = "2023-07-02T14:51:24.045162-07:00"
MOCK_TELEGRAMS = [
    {
        # None since CEMIHandler is mocked away and doesn't
        # set it to False
        "data_secure": None,
        "destination": "1/3/4",
        "destination_name": "",
        "direction": "Incoming",
        "dpt_main": None,
        "dpt_sub": None,
        "dpt_name": None,
        "payload": True,
        "source": "1.2.3",
        "source_name": "",
        "telegramtype": "GroupValueWrite",
        "timestamp": MOCK_TIMESTAMP,
        "unit": None,
        "value": None,
    },
    {
        "data_secure": None,
        "destination": "2/2/2",
        "destination_name": "",
        "direction": "Outgoing",
        "dpt_main": None,
        "dpt_sub": None,
        "dpt_name": None,
        "payload": [1, 2, 3, 4],
        "source": "0.0.0",
        "source_name": "Home Assistant",
        "telegramtype": "GroupValueWrite",
        "timestamp": MOCK_TIMESTAMP,
        "unit": None,
        "value": None,
    },
]


def assert_telegram_history(telegrams: list[TelegramDict]) -> bool:
    """Assert mock telegrams equal the given telegrams, omitting timestamp."""
    assert len(telegrams) == len(MOCK_TELEGRAMS)
    for index, value in enumerate(telegrams):
        test_telegram = copy(value)  # don't modify the original
        comp_telegram = MOCK_TELEGRAMS[index]
        assert datetime.fromisoformat(test_telegram["timestamp"])
        if isinstance(test_telegram["payload"], tuple):
            # JSON encodes tuples to lists
            test_telegram["payload"] = list(test_telegram["payload"])  # type: ignore[typeddict-item]
        assert test_telegram | {"timestamp": MOCK_TIMESTAMP} == comp_telegram
    return True


async def test_store_telegram_history(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test storing telegram history."""
    await knx.setup_integration()
    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams

    await knx.receive_write("1/3/4", True)
    await hass.services.async_call(
        DOMAIN, "send", {"address": "2/2/2", "payload": [1, 2, 3, 4]}, blocking=True
    )
    await knx.assert_write("2/2/2", (1, 2, 3, 4))

    # Wait for async store task
    await hass.async_block_till_done()

    # Verify in Memory store
    assert telegrams_module.store is not None
    result = await telegrams_module.store.query(
        TelegramQuery(order_descending=False),
        flush_first=True,
    )
    assert len(result.telegrams) == 2
    assert result.telegrams[0].destination == "1/3/4"
    assert result.telegrams[1].destination == "2/2/2"


async def test_store_telegram_history_sqlite(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test storing telegram history in SQLite."""
    await knx.setup_integration()
    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams

    await knx.receive_write("1/3/4", True)
    await hass.async_block_till_done()

    # Verify in SQLite store
    assert telegrams_module.store is not None
    result = await telegrams_module.store.query(
        TelegramQuery(),
        flush_first=True,
    )
    assert len(result.telegrams) == 1
    assert result.telegrams[0].destination == "1/3/4"


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(KnxTelegramStoreException("DB init failure"), id="db_error"),
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(ValueError("unexpected"), id="generic_error"),
    ],
)
async def test_store_telegram_history_error_handling(
    hass: HomeAssistant,
    knx: KNXTestKit,
    side_effect: Exception,
) -> None:
    """Test storage initialization handling for the different failure modes."""
    with patch(
        "knx_telegram_store.BufferedSqliteStore.initialize",
        side_effect=side_effect,
    ):
        await knx.setup_integration()

    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is None

    # Check that the repair issue was created
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR)
    assert issue is not None


async def test_store_telegram_history_needs_migration_timeout(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test that store initialization is aborted when needs_migration times out."""

    async def hanging_probe() -> bool:
        await asyncio.Event().wait()
        return False

    with (
        patch("homeassistant.components.knx.telegrams.STORE_INIT_TIMEOUT", 0.05),
        patch(
            "knx_telegram_store.BufferedSqliteStore.needs_migration",
            side_effect=hanging_probe,
        ),
    ):
        await knx.setup_integration()

    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is None

    # Check that the repair issue was created
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR)
    assert issue is not None


async def test_migrate_telegrams_from_json(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test legacy JSON telegram history is migrated into the store."""
    fixture = await async_load_json_object_fixture(
        hass, "telegrams_history.json", DOMAIN
    )
    json_telegrams = fixture["data"]
    history_key = "knx/telegrams_history.json"
    knx.hass_storage[history_key] = {
        "version": 1,
        "minor_version": 1,
        "key": history_key,
        "data": json_telegrams,
    }

    await knx.setup_integration()

    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is not None
    result = await telegrams_module.store.query(TelegramQuery(), flush_first=True)
    assert result.total_count == len(json_telegrams)
    # The legacy JSON store is removed after a successful migration
    assert history_key not in knx.hass_storage


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(KnxTelegramStoreException("stop failed"), id="db_error"),
        pytest.param(ValueError("unexpected"), id="generic_error"),
    ],
)
async def test_stop_error_handling(
    hass: HomeAssistant,
    knx: KNXTestKit,
    side_effect: Exception,
) -> None:
    """Test that errors while stopping the store are swallowed."""
    await knx.setup_integration()

    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is not None

    # An error on stop must not propagate
    with patch.object(telegrams_module.store, "stop", side_effect=side_effect):
        await telegrams_module.stop()


@pytest.mark.usefixtures("load_knxproj")
async def test_model_to_dict_resolution(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test model_to_dict name resolution and DPT handling."""
    await knx.setup_integration()
    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.project.loaded

    # Names are resolved from the loaded project when not set on the telegram,
    # and an unresolvable DPT yields None name/unit.
    from_project = StoredTelegram(
        timestamp=dt_util.now(),
        source="1.0.0",
        destination="0/0/1",
        direction="Incoming",
        telegramtype="GroupValueWrite",
        payload=(1,),
        value="on",
        value_numeric=None,
        dpt_main=999,
        dpt_sub=1,
        source_name="",
        destination_name="",
        data_secure=False,
    )
    result = telegrams_module.model_to_dict(from_project)
    assert (
        result["source_name"] == "Weinzierl Engineering GmbH KNX IP Router 752 secure"
    )
    assert result["destination_name"] == "Binary"
    assert result["dpt_name"] is None
    assert result["unit"] is None

    # Outgoing telegram from an unknown source falls back to "Home Assistant".
    outgoing = StoredTelegram(
        timestamp=dt_util.now(),
        source="0.0.0",
        destination="1/2/3",
        direction="Outgoing",
        telegramtype="GroupValueWrite",
        payload=(1,),
        value="on",
        value_numeric=None,
        dpt_main=None,
        dpt_sub=None,
        source_name="",
        destination_name="",
        data_secure=False,
    )
    result = telegrams_module.model_to_dict(outgoing)
    assert result["source_name"] == "Home Assistant"

    # A telegram with DPT info resolves the transcoder name and unit, and
    # explicit names are preserved as-is.
    with_dpt = StoredTelegram(
        timestamp=dt_util.now(),
        source="1.0.32",
        destination="1/2/11",
        direction="Incoming",
        telegramtype="GroupValueWrite",
        payload=(7, 158),
        value=19.5,
        value_numeric=19.5,
        dpt_main=9,
        dpt_sub=1,
        source_name="Sensor",
        destination_name="Temperature",
        data_secure=False,
    )
    result = telegrams_module.model_to_dict(with_dpt)
    assert result["source_name"] == "Sensor"
    assert result["destination_name"] == "Temperature"
    assert result["dpt_name"] == "temperature"
    assert result["unit"] == "°C"


async def test_load_history_needs_migration(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test the schema-migration branch of store initialization."""
    with patch(
        "knx_telegram_store.BufferedSqliteStore.needs_migration",
        return_value=True,
    ):
        await knx.setup_integration()

    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is not None


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(KnxTelegramStoreException("hydrate failed"), id="db_error"),
        pytest.param(ValueError("unexpected"), id="generic_error"),
    ],
)
async def test_load_history_hydrate_error(
    hass: HomeAssistant,
    knx: KNXTestKit,
    side_effect: Exception,
) -> None:
    """Test that errors while hydrating last_ga_telegrams are swallowed."""
    with patch(
        "knx_telegram_store.BufferedSqliteStore.get_last_unique_telegrams",
        side_effect=side_effect,
    ):
        await knx.setup_integration()

    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is not None
    assert telegrams_module.last_ga_telegrams == {}


async def test_migrate_telegrams_no_json(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test migration is a no-op when there is no legacy JSON history."""
    await knx.setup_integration()

    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is not None
    result = await telegrams_module.store.query(TelegramQuery(), flush_first=True)
    assert result.total_count == 0


async def test_migrate_telegrams_unexpected_format(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test migration skips an unexpected legacy JSON payload format."""
    history_key = "knx/telegrams_history.json"
    knx.hass_storage[history_key] = {
        "version": 1,
        "minor_version": 1,
        "key": history_key,
        "data": "not a list or dict",
    }

    await knx.setup_integration()

    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is not None
    result = await telegrams_module.store.query(TelegramQuery(), flush_first=True)
    assert result.total_count == 0


async def test_migrate_telegrams_store_error(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test migration errors are logged without failing setup."""
    history_key = "knx/telegrams_history.json"
    knx.hass_storage[history_key] = {
        "version": 1,
        "minor_version": 1,
        "key": history_key,
        "data": [
            {
                "destination": "1/1/1",
                "source": "1.0.1",
                "direction": "Incoming",
                "payload": [1],
                "telegramtype": "GroupValueWrite",
                "timestamp": MOCK_TIMESTAMP,
                "value": 1,
                "source_name": "",
                "destination_name": "",
                "data_secure": False,
                "dpt_main": 1,
                "dpt_sub": 1,
                "dpt_name": "switch",
                "unit": None,
            }
        ],
    }

    with patch(
        "knx_telegram_store.BufferedSqliteStore.store_many",
        side_effect=KnxTelegramStoreException("write failed"),
    ):
        await knx.setup_integration()

    # Setup still succeeds even though migration failed
    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is not None


async def test_nightly_eviction_calls_evict_expired(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test expired telegrams are evicted on the nightly 3 AM run."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2024-01-01 12:00:00+00:00")
    await knx.setup_integration()
    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is not None

    with patch.object(
        telegrams_module.store,
        "evict_expired",
        new=AsyncMock(wraps=telegrams_module.store.evict_expired),
    ) as evict_expired:
        # Nothing should happen before 3 AM
        freezer.move_to("2024-01-02 02:59:00+00:00")
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        evict_expired.assert_not_called()

        freezer.move_to("2024-01-02 03:00:00+00:00")
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        evict_expired.assert_called_once()


async def test_nightly_eviction_zero_retention_deletes_all(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a retention of 0 days deletes all telegrams on the nightly run."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2024-01-01 12:00:00+00:00")
    knx.mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        knx.mock_config_entry,
        options=knx.mock_config_entry.options
        | {CONF_KNX_TELEGRAM_DB_RETENTION_DAYS: 0},
    )
    await knx.setup_integration(add_entry_to_hass=False)
    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is not None

    await knx.receive_write("1/3/4", True)
    await hass.async_block_till_done()
    result = await telegrams_module.store.query(TelegramQuery(), flush_first=True)
    assert len(result.telegrams) == 1

    freezer.move_to("2024-01-02 03:00:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    result = await telegrams_module.store.query(TelegramQuery(), flush_first=True)
    assert len(result.telegrams) == 0


async def test_nightly_eviction_error_handling(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a store error during nightly eviction is logged and does not raise."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2024-01-01 12:00:00+00:00")
    await knx.setup_integration()
    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is not None

    with patch.object(
        telegrams_module.store,
        "evict_expired",
        new=AsyncMock(side_effect=KnxTelegramStoreException("evict failed")),
    ):
        freezer.move_to("2024-01-02 03:00:00+00:00")
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert "Database error evicting expired KNX telegrams" in caplog.text
    # Store remains operational after the failed eviction
    assert telegrams_module.store is not None


async def test_postgres_backend_init_error(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test PostgreSQL backend DSN handling and init failure path."""
    dsn = "postgresql://user:secret@db.local:5432/knx"
    knx.mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        knx.mock_config_entry,
        options=knx.mock_config_entry.options
        | {
            CONF_KNX_TELEGRAM_DB_BACKEND: KNX_TELEGRAM_BACKEND_POSTGRES,
            CONF_KNX_TELEGRAM_DB_POSTGRES_DSN: dsn,
        },
    )

    # Mock the store to avoid constructing a real SQLAlchemy engine / connecting.
    mock_store = AsyncMock()
    mock_store.needs_migration.return_value = False
    mock_store.initialize.side_effect = KnxTelegramStoreException("no server")
    with patch(
        "homeassistant.components.knx.telegrams.BufferedPostgresStore",
        return_value=mock_store,
    ):
        await knx.setup_integration(add_entry_to_hass=False)

    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is None

    issue_registry = ir.async_get(hass)
    assert (
        issue_registry.async_get_issue(DOMAIN, REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR)
        is not None
    )
