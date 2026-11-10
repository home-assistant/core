"""KNX Telegrams Tests."""

from __future__ import annotations

import asyncio
from contextlib import AbstractContextManager
from copy import copy
from datetime import datetime
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from knx_telegram_store import (
    BufferedPostgresStore,
    BufferedSqliteStore,
    KnxTelegramStoreException,
    StoredTelegram,
    TelegramQuery,
)
import pytest
from pytest_homeassistant.common import (
    async_fire_time_changed,
    async_load_json_object_fixture,
)
from xknx.exceptions import XKNXException
from xknx.telegram import Telegram, TelegramDirection
from xknx.telegram.address import GroupAddress, IndividualAddress
from xknx.telegram.apci import GroupValueRead

from homeassistant.components.knx.const import (
    CONF_KNX_TELEGRAM_DB_BACKEND,
    CONF_KNX_TELEGRAM_DB_POSTGRES_DSN,
    CONF_KNX_TELEGRAM_DB_RETENTION_DAYS,
    DOMAIN,
    KNX_MODULE_KEY,
    KNX_TELEGRAM_BACKEND_POSTGRES,
    REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR,
)
from homeassistant.components.knx.telegrams import (
    FLUSH_INTERVAL_SECONDS_POSTGRES,
    FLUSH_INTERVAL_SECONDS_SQLITE,
    TelegramDict,
    Telegrams,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .conftest import KNXTestKit

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
    await knx.setup_integration(real_telegram_store=True)
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


@pytest.mark.parametrize(
    ("time_zone", "timestamp"),
    [
        pytest.param("UTC", "2024-07-01T12:00:00.123456+00:00", id="utc"),
        pytest.param(
            "Europe/Berlin", "2024-07-01T14:00:00.123456+02:00", id="berlin-summer"
        ),
        pytest.param(
            "Europe/Berlin", "2024-01-01T13:00:00.123456+01:00", id="berlin-winter"
        ),
        pytest.param(
            "America/New_York", "2024-07-01T08:00:00.123456-04:00", id="new-york"
        ),
    ],
)
async def test_store_telegram_history_sqlite(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
    time_zone: str,
    timestamp: str,
) -> None:
    """Test SQLite history preserves the live timestamp, including its time zone."""
    await hass.config.async_set_time_zone(time_zone)
    freezer.move_to(timestamp)
    await knx.setup_integration(real_telegram_store=True)
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
    assert telegrams_module.last_ga_telegrams["1/3/4"]["timestamp"] == timestamp
    assert telegrams_module.model_to_dict(result.telegrams[0])["timestamp"] == timestamp


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(KnxTelegramStoreException("DB init failure"), id="db_error"),
        pytest.param(ValueError("unexpected"), id="generic_error"),
    ],
)
async def test_store_telegram_history_error_handling(
    hass: HomeAssistant,
    knx: KNXTestKit,
    issue_registry: ir.IssueRegistry,
    side_effect: Exception,
) -> None:
    """Test storage initialization handling for the different failure modes."""
    with patch(
        "knx_telegram_store.BufferedSqliteStore.initialize",
        side_effect=side_effect,
    ):
        await knx.setup_integration(real_telegram_store=True)

    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is None

    # Check that the repair issue was created
    issue = issue_registry.async_get_issue(DOMAIN, REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR)
    assert issue is not None
    assert issue.config_entry_id == knx.mock_config_entry.entry_id

    await hass.config_entries.async_remove(knx.mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        issue_registry.async_get_issue(DOMAIN, REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR)
        is None
    )


async def test_sqlite_store_is_told_the_configured_timezone(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test the SQLite store receives Home Assistant's configured time zone."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    await knx.setup_integration(real_telegram_store=True)

    store = hass.data[KNX_MODULE_KEY].telegrams.store
    assert store is not None
    # The zone the store was handed, read back off the real store rather than
    # off a mock: the store fixture rebuilds the class during setup, so a patch
    # placed around setup_integration never sees the call.
    assert store._legacy_timestamp_timezone is dt_util.get_default_time_zone()


async def test_store_initializes_in_background(
    hass: HomeAssistant,
    knx: KNXTestKit,
    issue_registry: ir.IssueRegistry,
) -> None:
    """KNX starts while the store initializes; telegrams received meanwhile are kept."""
    release_initialize = asyncio.Event()
    original_initialize = BufferedSqliteStore.initialize

    async def slow_initialize(self: BufferedSqliteStore) -> None:
        await release_initialize.wait()
        await original_initialize(self)

    with patch.object(BufferedSqliteStore, "initialize", slow_initialize):
        await knx.setup_integration(
            real_telegram_store=True, wait_for_telegram_store=False
        )
        telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
        assert telegrams_module.store is None

        # The KNX connection is up and telegrams are handled without the store.
        await knx.receive_write("1/3/4", True)
        assert telegrams_module.last_ga_telegrams["1/3/4"]["payload"] is True
        assert len(telegrams_module._uninitialized_store._buffer) == 1

        release_initialize.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert telegrams_module.store is not None
    assert telegrams_module._uninitialized_store is None
    assert (
        issue_registry.async_get_issue(DOMAIN, REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR)
        is None
    )
    result = await telegrams_module.store.query(TelegramQuery(), flush_first=True)
    assert [t.destination for t in result.telegrams] == ["1/3/4"]
    assert telegrams_module.last_ga_telegrams["1/3/4"]["payload"] is True


async def test_stop_cancels_in_flight_store_init(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Unloading while the store is still initializing cancels it cleanly."""

    async def hanging_initialize(self: BufferedSqliteStore) -> None:
        await asyncio.Event().wait()

    with patch.object(BufferedSqliteStore, "initialize", hanging_initialize):
        await knx.setup_integration(
            real_telegram_store=True, wait_for_telegram_store=False
        )
        telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
        assert telegrams_module.store is None

        assert await hass.config_entries.async_unload(knx.mock_config_entry.entry_id)
        assert KNX_MODULE_KEY not in hass.data

    assert telegrams_module._store_init_task is None
    assert telegrams_module._uninitialized_store is None


async def test_failed_setup_stops_the_store_initialization(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """A setup that fails after the store started initializing tears the store down.

    The entry is not unloaded on a failed setup, and the retry builds a new store
    on the same database, so the first initialization must not keep running.
    """
    handlers: list[Telegrams] = []
    original_async_start = Telegrams.async_start

    def recording_async_start(self: Telegrams) -> None:
        handlers.append(self)
        original_async_start(self)

    async def hanging_initialize(self: BufferedSqliteStore) -> None:
        await asyncio.Event().wait()

    with (
        patch.object(Telegrams, "async_start", recording_async_start),
        patch.object(BufferedSqliteStore, "initialize", hanging_initialize),
        patch("xknx.xknx.XKNX.start", side_effect=XKNXException("no gateway")),
    ):
        await knx.setup_integration(
            real_telegram_store=True, wait_for_telegram_store=False
        )

    assert knx.mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    (telegrams,) = handlers
    assert telegrams._store_init_task is None
    assert telegrams._uninitialized_store is None
    assert telegrams.store is None
    # The entry's unload hooks and the module's stop may both run; the second is a no-op.
    await telegrams.stop()


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

    await knx.setup_integration(real_telegram_store=True)

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
    await knx.setup_integration(real_telegram_store=True)

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
    await knx.setup_integration(real_telegram_store=True)
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


@pytest.mark.usefixtures("load_knxproj")
async def test_telegram_to_dict_dpt_from_project(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test undecodable telegrams get their DPT from the project."""
    await knx.setup_integration()
    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.project.loaded

    def read_telegram(destination: str) -> TelegramDict:
        return telegrams_module.telegram_to_dict(
            Telegram(
                destination_address=GroupAddress(destination),
                direction=TelegramDirection.INCOMING,
                payload=GroupValueRead(),
                source_address=IndividualAddress("1.2.3"),
            )
        )

    # GroupValueRead has no payload to decode - the DPT of the group address
    # is still reported from the project, without a value.
    result = read_telegram("0/0/1")
    assert result["telegramtype"] == "GroupValueRead"
    assert result["dpt_main"] == 1
    assert result["dpt_sub"] == 1
    assert result["dpt_name"] == "switch"
    assert result["payload"] is None
    assert result["value"] is None

    # Group addresses unknown to the project stay without DPT.
    result = read_telegram("7/7/7")
    assert result["dpt_main"] is None
    assert result["dpt_sub"] is None
    assert result["dpt_name"] is None


@pytest.mark.parametrize(
    "needs_migration",
    [
        pytest.param(True, id="needs_migration"),
        pytest.param(False, id="no_migration"),
    ],
)
async def test_load_history_runs_in_its_own_task(
    hass: HomeAssistant,
    knx: KNXTestKit,
    needs_migration: bool,
) -> None:
    """Store initialization runs in a background task the bootstrap timeout cannot cancel."""
    original_initialize = BufferedSqliteStore.initialize
    seen: list[tuple[str | None, bool]] = []

    async def initialize(self: BufferedSqliteStore) -> None:
        task = asyncio.current_task()
        seen.append((task.get_name() if task else None, DOMAIN in hass.timeout.zones))
        await original_initialize(self)

    with (
        patch(
            "knx_telegram_store.BufferedSqliteStore.needs_migration",
            return_value=needs_migration,
        ),
        patch.object(BufferedSqliteStore, "initialize", initialize),
    ):
        await knx.setup_integration(real_telegram_store=True)

    # Off the setup task, so no timeout freeze is needed to protect a migration.
    assert seen == [("KNX telegram store initialization", False)]
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
        await knx.setup_integration(real_telegram_store=True)

    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is not None
    assert telegrams_module.last_ga_telegrams == {}


async def test_migrate_telegrams_no_json(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test migration is a no-op when there is no legacy JSON history."""
    await knx.setup_integration(real_telegram_store=True)

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

    await knx.setup_integration(real_telegram_store=True)

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
        await knx.setup_integration(real_telegram_store=True)

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
    await knx.setup_integration(real_telegram_store=True)
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
    await knx.setup_integration(add_entry_to_hass=False, real_telegram_store=True)
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
    await knx.setup_integration(real_telegram_store=True)
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
    issue_registry: ir.IssueRegistry,
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

    with _patch_postgres_store(
        initialize=AsyncMock(side_effect=KnxTelegramStoreException("no server"))
    ):
        await knx.setup_integration(add_entry_to_hass=False, real_telegram_store=True)

    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert telegrams_module.store is None

    assert (
        issue_registry.async_get_issue(DOMAIN, REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR)
        is not None
    )


POSTGRES_OPTIONS = {
    CONF_KNX_TELEGRAM_DB_BACKEND: KNX_TELEGRAM_BACKEND_POSTGRES,
    CONF_KNX_TELEGRAM_DB_POSTGRES_DSN: "postgresql://user:secret@db.local:5432/knx",
}


def _connect_error(cause: BaseException | None) -> KnxTelegramStoreException:
    """Return a store exception wrapping a driver error, as the library raises it."""
    error = KnxTelegramStoreException("connect failed")
    error.__cause__ = cause
    return error


def _patch_postgres_store(initialize: AsyncMock) -> AbstractContextManager[None]:
    """Keep the PostgreSQL store off the network; the engine itself never connects.

    Patched on the class: the test kit re-patches the module attribute during
    setup, so a patched constructor would not be the one called.
    """
    return patch.multiple(
        BufferedPostgresStore,
        needs_migration=AsyncMock(return_value=False),
        initialize=initialize,
        get_last_unique_telegrams=AsyncMock(return_value=[]),
    )


@pytest.mark.parametrize(
    ("cause", "attempts", "store_available"),
    [
        pytest.param(
            ConnectionRefusedError(111, "Connection refused"),
            2,
            True,
            id="refused_then_reachable",
        ),
        pytest.param(TimeoutError(), 2, True, id="timeout_then_reachable"),
        pytest.param(ValueError("bad dsn"), 1, False, id="other_error_not_retried"),
        pytest.param(None, 1, False, id="no_cause_not_retried"),
    ],
)
async def test_postgres_store_init_retries_unreachable_server(
    hass: HomeAssistant,
    knx: KNXTestKit,
    issue_registry: ir.IssueRegistry,
    cause: BaseException | None,
    attempts: int,
    store_available: bool,
) -> None:
    """An unreachable PostgreSQL server is retried; other errors are final."""
    knx.mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        knx.mock_config_entry,
        options=knx.mock_config_entry.options | POSTGRES_OPTIONS,
    )
    initialize = AsyncMock(side_effect=[_connect_error(cause), None])
    with (
        patch(
            "homeassistant.components.knx.telegrams.STORE_CONNECT_RETRY_BACKOFF", (0,)
        ),
        _patch_postgres_store(initialize),
    ):
        await knx.setup_integration(add_entry_to_hass=False, real_telegram_store=True)

    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert initialize.call_count == attempts
    assert (telegrams_module.store is not None) == store_available
    assert (
        issue_registry.async_get_issue(DOMAIN, REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR)
        is None
    ) == store_available


async def test_postgres_store_init_gives_up_after_retries(
    hass: HomeAssistant,
    knx: KNXTestKit,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A PostgreSQL server that stays unreachable disables the store after the backoff."""
    knx.mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        knx.mock_config_entry,
        options=knx.mock_config_entry.options | POSTGRES_OPTIONS,
    )
    initialize = AsyncMock(
        side_effect=_connect_error(ConnectionRefusedError(111, "Connection refused"))
    )
    with (
        patch(
            "homeassistant.components.knx.telegrams.STORE_CONNECT_RETRY_BACKOFF", (0, 0)
        ),
        _patch_postgres_store(initialize),
    ):
        await knx.setup_integration(add_entry_to_hass=False, real_telegram_store=True)

    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams
    assert initialize.call_count == 3
    assert telegrams_module.store is None
    assert (
        issue_registry.async_get_issue(DOMAIN, REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR)
        is not None
    )


async def test_postgres_backend_flushes_more_often_than_sqlite(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Postgres flushes every second; sqlite keeps the original 10 minute interval.

    Sqlite's long interval is safe because the websocket history API already
    flushes on demand. Postgres consumers that only learn about a telegram
    once it is written (e.g. a LISTEN/NOTIFY-driven live view) have no such
    fallback, so they need a much shorter interval.
    """
    assert FLUSH_INTERVAL_SECONDS_POSTGRES < FLUSH_INTERVAL_SECONDS_SQLITE

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
    await knx.setup_integration(add_entry_to_hass=False)

    store = hass.data[KNX_MODULE_KEY].telegrams.store
    assert store.flush_interval == FLUSH_INTERVAL_SECONDS_POSTGRES


async def test_sqlite_backend_keeps_long_flush_interval(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Sqlite's flush interval is unaffected by the Postgres-specific tuning."""
    await knx.setup_integration()

    store = hass.data[KNX_MODULE_KEY].telegrams.store
    assert store.flush_interval == FLUSH_INTERVAL_SECONDS_SQLITE
