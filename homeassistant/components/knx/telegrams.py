"""KNX Telegrams history and storage."""

import asyncio
import contextlib
from datetime import datetime
import logging
import os
from typing import Any, TypedDict

from knx_telegram_store import (
    BufferedPostgresStore,
    BufferedSqliteStore,
    KnxTelegramStoreException,
    StoredTelegram,
)
from xknx import XKNX
from xknx.dpt import DPTArray, DPTBase, DPTBinary
from xknx.dpt.dpt import DPTComplexData, DPTEnumData
from xknx.exceptions import XKNXException
from xknx.telegram import Telegram, TelegramDirection
from xknx.telegram.apci import GroupValueResponse, GroupValueWrite

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import STORAGE_DIR, Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_KNX_TELEGRAM_DB_BACKEND,
    CONF_KNX_TELEGRAM_DB_POSTGRES_DSN,
    CONF_KNX_TELEGRAM_DB_RETENTION_DAYS,
    KNX_TELEGRAM_BACKEND_POSTGRES,
    KNX_TELEGRAM_DB_PATH_SQLITE,
    SIGNAL_KNX_DATA_SECURE_ISSUE_TELEGRAM,
    SIGNAL_KNX_TELEGRAM,
    KNXConfigEntryOptions,
)
from .project import KNXProject
from .repairs import (
    async_create_telegram_storage_issue,
    async_delete_telegram_storage_issue,
)

_LOGGER = logging.getLogger(__name__)

# Hour of the day (local time) at which expired telegrams are evicted nightly.
EVICT_EXPIRED_HOUR = 3

# Interval at which buffered telegram writes are flushed to the database.
# Websocket queries flush on demand (``flush_first=True``), so the only telegrams
# at risk from a longer interval are those buffered during an ungraceful shutdown.
FLUSH_INTERVAL_SECONDS = 600

# The buffer drops the oldest telegrams when full. Size it to cover a full
# flush interval at ~50 telegrams/s, the maximum rate of a KNX TP line, so
# nothing is dropped while the database is healthy.
MAX_BUFFER_TELEGRAMS = FLUSH_INTERVAL_SECONDS * 50

# Timeout for the migration probe and store initialization, so an unreachable
# database cannot block KNX setup until the driver/OS connection timeout expires.
STORE_INIT_TIMEOUT = 10


class DecodedTelegramPayload(TypedDict):
    """Decoded payload value and metadata."""

    dpt_main: int | None
    dpt_sub: int | None
    dpt_name: str | None
    unit: str | None
    value: bool | str | int | float | dict[str, str | int | float | bool] | None


class TelegramDict(DecodedTelegramPayload):
    """Represent a Telegram as a dict."""

    # this has to be in sync with the frontend implementation
    data_secure: bool | None
    destination: str
    destination_name: str
    direction: str
    payload: int | tuple[int, ...] | None
    source: str
    source_name: str
    telegramtype: str
    timestamp: str  # ISO format


class Telegrams:
    """Class to handle KNX telegrams."""

    def __init__(
        self,
        hass: HomeAssistant,
        xknx: XKNX,
        project: KNXProject,
        config: KNXConfigEntryOptions,
    ) -> None:
        """Initialize Telegrams class."""
        self.hass = hass
        self.project = project
        self.config = config

        self.backend: str = config[CONF_KNX_TELEGRAM_DB_BACKEND]
        self.dsn: str = str(config.get(CONF_KNX_TELEGRAM_DB_POSTGRES_DSN, ""))
        self.retention_days: int = config[CONF_KNX_TELEGRAM_DB_RETENTION_DAYS]

        self.store: BufferedSqliteStore | BufferedPostgresStore | None = None
        self._uninitialized_store: (
            BufferedSqliteStore | BufferedPostgresStore | None
        ) = None
        self._evict_expired_unsub: CALLBACK_TYPE | None = None

        if self.backend == KNX_TELEGRAM_BACKEND_POSTGRES:
            self._uninitialized_store = BufferedPostgresStore(
                self.dsn,
                retention_days=self.retention_days,
                flush_interval=FLUSH_INTERVAL_SECONDS,
                max_buffer_size=MAX_BUFFER_TELEGRAMS,
            )
        else:
            full_path = hass.config.path(STORAGE_DIR, KNX_TELEGRAM_DB_PATH_SQLITE)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            self._uninitialized_store = BufferedSqliteStore(
                full_path,
                retention_days=self.retention_days,
                flush_interval=FLUSH_INTERVAL_SECONDS,
                max_buffer_size=MAX_BUFFER_TELEGRAMS,
            )

        self._xknx_telegram_cb_handle = (
            xknx.telegram_queue.register_telegram_received_cb(
                telegram_received_cb=self._xknx_telegram_cb,
                match_for_outgoing=True,
            )
        )
        self._xknx_data_secure_group_key_issue_cb_handle = (
            xknx.telegram_queue.register_data_secure_group_key_issue_cb(
                self._xknx_data_secure_group_key_issue_cb,
            )
        )
        self.last_ga_telegrams: dict[str, TelegramDict] = {}

    async def load_history(self) -> None:
        """Load history from store."""
        if self._uninitialized_store is None:
            return
        try:
            async with asyncio.timeout(STORE_INIT_TIMEOUT):
                needs_migration = await self._uninitialized_store.needs_migration()
            if needs_migration:
                _LOGGER.warning(
                    "KNX telegram history database schema upgrade/migration is required. "
                    "This may take some time depending on your database size. Please do not restart Home Assistant"
                )
                await self._uninitialized_store.initialize()
            else:
                _LOGGER.debug(
                    "Initializing KNX telegram storage backend '%s'",
                    self.backend,
                )
                async with asyncio.timeout(STORE_INIT_TIMEOUT):
                    await self._uninitialized_store.initialize()
            _LOGGER.info(
                "Successfully initialized KNX telegram storage backend '%s'",
                self.backend,
            )
        except TimeoutError:
            _LOGGER.error(
                "Timeout initializing KNX telegram storage backend '%s'",
                self.backend,
            )
            await self._abort_store_init()
            return
        except KnxTelegramStoreException as err:
            _LOGGER.error(
                "Database error initializing KNX telegram storage backend '%s': %s",
                self.backend,
                err,
            )
            await self._abort_store_init()
            return
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Error initializing KNX telegram storage backend '%s': %s",
                self.backend,
                err,
            )
            await self._abort_store_init()
            return
        async_delete_telegram_storage_issue(self.hass)
        self.store = self._uninitialized_store
        self.store.start()
        self._uninitialized_store = None

        # Evict telegrams older than the retention period once a night. A
        # retention of 0 days means all telegrams are deleted on each run.
        self._evict_expired_unsub = async_track_time_change(
            self.hass,
            self._async_evict_expired,
            hour=EVICT_EXPIRED_HOUR,
            minute=0,
            second=0,
        )

        # Migrate legacy JSON storage if it exists
        await self.migrate_telegrams()

        # Hydrate last_ga_telegrams from store
        try:
            result = await self.store.get_last_unique_telegrams()
        except KnxTelegramStoreException as err:
            _LOGGER.warning("Database error hydrating last_ga_telegrams: %s", err)
            return
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Error hydrating last_ga_telegrams: %s", err)
            return
        for m in result:
            if m.payload is not None:
                t_dict = self.model_to_dict(m)
                self.last_ga_telegrams[t_dict["destination"]] = t_dict
        _LOGGER.debug("Hydrated %d unique telegrams from store", len(result))

    async def _abort_store_init(self) -> None:
        """Create a repair issue and tear down a store that failed to init."""
        async_create_telegram_storage_issue(self.hass)
        if self._uninitialized_store is not None:
            with contextlib.suppress(Exception):
                await self._uninitialized_store.close()
        self._uninitialized_store = None

    async def _async_evict_expired(self, now: datetime) -> None:
        """Delete telegrams older than the configured retention period."""
        if self.store is None:
            return
        try:
            deleted = await self.store.evict_expired()
        except KnxTelegramStoreException as err:
            _LOGGER.warning("Database error evicting expired KNX telegrams: %s", err)
            return
        _LOGGER.debug("Evicted %d expired KNX telegrams from storage", deleted)

    async def stop(self) -> None:
        """Stop history store."""
        if self._evict_expired_unsub is not None:
            self._evict_expired_unsub()
            self._evict_expired_unsub = None
        if self.store is None:
            return
        try:
            await self.store.stop()
        except KnxTelegramStoreException as err:
            _LOGGER.warning(
                "Database error stopping KNX telegram storage backend: %s", err
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Error stopping KNX telegram storage backend: %s", err)

    def _xknx_telegram_cb(self, telegram: Telegram) -> None:
        """Handle incoming and outgoing telegrams from xknx."""
        telegram_dict = self.telegram_to_dict(telegram)
        if telegram_dict["payload"] is not None:
            # exclude GroupValueRead telegrams
            self.last_ga_telegrams[telegram_dict["destination"]] = telegram_dict

        # Store in history store
        if self.store is not None:
            self.store.store_sync(self.dict_to_model(telegram_dict))

        async_dispatcher_send(self.hass, SIGNAL_KNX_TELEGRAM, telegram, telegram_dict)

    def _xknx_data_secure_group_key_issue_cb(self, telegram: Telegram) -> None:
        """Handle telegrams with undecodable data secure payload from xknx."""
        telegram_dict = self.telegram_to_dict(telegram)

        # Store in history store
        if self.store is not None:
            self.store.store_sync(self.dict_to_model(telegram_dict))

        async_dispatcher_send(
            self.hass, SIGNAL_KNX_DATA_SECURE_ISSUE_TELEGRAM, telegram, telegram_dict
        )

    def telegram_to_dict(self, telegram: Telegram) -> TelegramDict:
        """Convert a Telegram to a dict."""
        dst_name = ""
        payload_data: int | tuple[int, ...] | None = None
        src_name = ""
        transcoder = None
        value = None

        if (
            ga_info := self.project.group_addresses.get(
                f"{telegram.destination_address}"
            )
        ) is not None:
            dst_name = ga_info.name

        if (
            device := self.project.devices.get(f"{telegram.source_address}")
        ) is not None:
            src_name = f"{device['manufacturer_name']} {device['name']}"
        elif telegram.direction is TelegramDirection.OUTGOING:
            src_name = "Home Assistant"

        if isinstance(telegram.payload, (GroupValueWrite, GroupValueResponse)):
            payload_data = telegram.payload.value.value

        if telegram.decoded_data is not None:
            transcoder = telegram.decoded_data.transcoder
            value = _serializable_decoded_data(telegram.decoded_data.value)

        return TelegramDict(
            data_secure=telegram.data_secure,
            destination=f"{telegram.destination_address}",
            destination_name=dst_name,
            direction=telegram.direction.value,
            dpt_main=transcoder.dpt_main_number if transcoder is not None else None,
            dpt_sub=transcoder.dpt_sub_number if transcoder is not None else None,
            dpt_name=transcoder.value_type if transcoder is not None else None,
            payload=payload_data,
            source=f"{telegram.source_address}",
            source_name=src_name,
            telegramtype=telegram.payload.__class__.__name__,
            timestamp=dt_util.now().isoformat(),
            unit=transcoder.unit if transcoder is not None else None,
            value=value,
        )

    def dict_to_model(self, t: TelegramDict) -> StoredTelegram:
        """Convert a TelegramDict to a StoredTelegram model."""
        value = t["value"]
        value_numeric: float | None = None
        if isinstance(value, (int, float)):
            value_numeric = float(value)

        payload: Any = t["payload"]
        if isinstance(payload, list):
            payload = tuple(payload)

        return StoredTelegram(
            timestamp=dt_util.parse_datetime(t["timestamp"], raise_on_error=True),
            source=t["source"],
            destination=t["destination"],
            direction=t["direction"],
            telegramtype=t["telegramtype"],
            payload=payload,
            value=value,
            value_numeric=value_numeric,
            dpt_main=t["dpt_main"],
            dpt_sub=t["dpt_sub"],
            source_name=t["source_name"],
            destination_name=t["destination_name"],
            data_secure=t["data_secure"],
        )

    async def migrate_telegrams(self) -> None:
        """Migrate telegrams from JSON storage to the current store."""

        if not isinstance(self.store, BufferedSqliteStore):
            return

        history_store = Store[Any](
            self.hass, version=1, key="knx/telegrams_history.json"
        )

        json_data = await history_store.async_load()
        if json_data is None:
            return

        _LOGGER.info("Migrating KNX telegram history from JSON to KNX Telegram Store")

        if not isinstance(json_data, list):
            _LOGGER.warning(
                "Unexpected format in KNX telegram history JSON, skipping migration"
            )
            return

        # Legacy JSON data from older HA instances might miss fields added later
        # (e.g., data_secure was added in 2026.3, value, payload, dpt_main/sub, names might also be missing)
        default_migration_values = {
            "value": None,
            "payload": None,
            "dpt_main": None,
            "dpt_sub": None,
            "source_name": "",
            "destination_name": "",
            "data_secure": False,
        }
        stored_telegrams = [
            self.dict_to_model(default_migration_values | t) for t in json_data
        ]
        try:
            if stored_telegrams:
                await self.store.store_many(stored_telegrams)
                _LOGGER.info(
                    "Successfully migrated %d telegrams", len(stored_telegrams)
                )

            await history_store.async_remove()
        except KnxTelegramStoreException as err:
            _LOGGER.error("Database error migrating KNX telegram history: %s", err)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error migrating KNX telegram history: %s", err)

    def model_to_dict(self, m: StoredTelegram) -> TelegramDict:
        """Convert a StoredTelegram model to a TelegramDict."""
        src_name = m.source_name
        if not src_name:
            if (device := self.project.devices.get(m.source)) is not None:
                src_name = f"{device['manufacturer_name']} {device['name']}"
            elif m.direction == TelegramDirection.OUTGOING.value:
                src_name = "Home Assistant"

        dst_name = m.destination_name
        if not dst_name:
            if (ga_info := self.project.group_addresses.get(m.destination)) is not None:
                dst_name = ga_info.name

        dpt_name, unit = self._resolve_dpt(m.dpt_main, m.dpt_sub)
        return TelegramDict(
            timestamp=m.timestamp.isoformat(),
            source=m.source,
            destination=m.destination,
            direction=m.direction,
            telegramtype=m.telegramtype,
            payload=m.payload,
            value=m.value,
            dpt_main=m.dpt_main,
            dpt_sub=m.dpt_sub,
            dpt_name=dpt_name,
            unit=unit,
            source_name=src_name,
            destination_name=dst_name,
            data_secure=m.data_secure,
        )

    def _resolve_dpt(
        self, main: int | None, sub: int | None
    ) -> tuple[str | None, str | None]:
        """Resolve DPT name and unit from main and sub numbers."""
        if main is None:
            return None, None
        if transcoder := DPTBase.parse_transcoder({"main": main, "sub": sub}):
            return transcoder.value_type, transcoder.unit
        return None, None


def _serializable_decoded_data(
    value: bool | float | str | DPTComplexData | DPTEnumData,
) -> bool | str | int | float | dict[str, str | int | float | bool]:
    """Return a serializable representation of decoded data."""
    if isinstance(value, DPTComplexData):
        return value.as_dict()
    if isinstance(value, DPTEnumData):
        return value.name.lower()
    return value


def decode_telegram_payload(
    payload: DPTArray | DPTBinary, transcoder: type[DPTBase]
) -> DecodedTelegramPayload:
    """Decode the payload of a KNX telegram with custom transcoder."""
    try:
        value = transcoder.from_knx(payload)
    except XKNXException:
        value = "Error decoding value"

    value = _serializable_decoded_data(value)

    return DecodedTelegramPayload(
        dpt_main=transcoder.dpt_main_number,
        dpt_sub=transcoder.dpt_sub_number,
        dpt_name=transcoder.value_type,
        unit=transcoder.unit,
        value=value,
    )
