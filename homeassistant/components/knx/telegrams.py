"""KNX Telegrams history and storage."""

import asyncio
from collections.abc import Callable
import contextlib
import logging
import os
from typing import Any, TypedDict

from knx_telegram_store import (
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

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import STORAGE_DIR, Store
from homeassistant.util import dt as dt_util
from homeassistant.util.signal_type import SignalType

from .const import (
    CONF_KNX_TELEGRAM_DB_PATH,
    CONF_KNX_TELEGRAM_DB_RETENTION_DAYS,
    DOMAIN,
    KNX_TELEGRAM_DB_PATH_DEFAULT,
    KNX_TELEGRAM_RETENTION_DEFAULT,
    REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR,
    KNXConfigEntryData,
)
from .project import KNXProject

_LOGGER = logging.getLogger(__name__)

# dispatcher signal for KNX interface device triggers
SIGNAL_KNX_TELEGRAM: SignalType[Telegram, TelegramDict] = SignalType("knx_telegram")
SIGNAL_KNX_DATA_SECURE_ISSUE_TELEGRAM: SignalType[Telegram, TelegramDict] = SignalType(
    "knx_data_secure_issue_telegram"
)


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
        config: KNXConfigEntryData,
    ) -> None:
        """Initialize Telegrams class."""
        self.hass = hass
        self.project = project
        self.config = config

        self.db_path: str = config.get(
            CONF_KNX_TELEGRAM_DB_PATH, KNX_TELEGRAM_DB_PATH_DEFAULT
        )
        self.retention_days: int = int(
            config.get(
                CONF_KNX_TELEGRAM_DB_RETENTION_DAYS, KNX_TELEGRAM_RETENTION_DEFAULT
            )
        )
        self.store: BufferedSqliteStore | None = None
        self._uninitialized_store: BufferedSqliteStore | None = None

        full_path = (
            self.db_path
            if self.db_path == ":memory:"
            else hass.config.path(STORAGE_DIR, self.db_path)
        )
        if full_path != ":memory:":
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
        self._uninitialized_store = BufferedSqliteStore(
            full_path,
            retention_days=self.retention_days,
            flush_interval=10.0,
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
        self._async_remove_listener: Callable[[], None] | None = None

    async def load_history(self) -> None:
        """Load history from store."""
        if self._uninitialized_store is None:
            return
        info = self._get_backend_info()
        try:
            needs_migration = await self._uninitialized_store.needs_migration()
            if needs_migration:
                _LOGGER.warning(
                    "KNX telegram history database schema upgrade/migration is required. "
                    "This may take some time depending on your database size. Please do not restart Home Assistant"
                )
                await self._uninitialized_store.initialize()
            else:
                _LOGGER.debug("Initializing KNX telegram storage (%s)", info)
                async with asyncio.timeout(10):
                    await self._uninitialized_store.initialize()
            _LOGGER.info("Successfully initialized KNX telegram storage")
        except TimeoutError:
            _LOGGER.error(
                "Timeout initializing KNX telegram storage (%s)",
                info,
            )
            await self._abort_store_init(info, "Timeout")
        except KnxTelegramStoreException as err:
            _LOGGER.error(
                "Database error initializing KNX telegram storage (%s): %s",
                info,
                err,
            )
            await self._abort_store_init(info, str(err))
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Error initializing KNX telegram storage (%s): %s",
                info,
                err,
            )
            await self._abort_store_init(info, str(err))
        else:
            ir.async_delete_issue(
                self.hass, DOMAIN, REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR
            )
            self.store = self._uninitialized_store
            self.store.start()
            self._uninitialized_store = None

        # Migrate legacy JSON storage if it exists
        await self.migrate_telegrams()

        # Hydrate last_ga_telegrams from store
        if self.store is not None:
            try:
                result = await self.store.get_last_unique_telegrams()
            except KnxTelegramStoreException as err:
                _LOGGER.warning("Database error hydrating last_ga_telegrams: %s", err)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Error hydrating last_ga_telegrams: %s", err)
            else:
                for m in result:
                    if m.payload is not None:
                        t_dict = self.model_to_dict(m)
                        self.last_ga_telegrams[t_dict["destination"]] = t_dict
                _LOGGER.debug("Hydrated %d unique telegrams from store", len(result))

    async def _abort_store_init(self, info: str, error: str) -> None:
        """Create a repair issue and tear down a store that failed to init."""
        self._create_repair_issue(info, error)
        if self._uninitialized_store is not None:
            with contextlib.suppress(Exception):
                await self._uninitialized_store.close()
        self._uninitialized_store = None

    def _create_repair_issue(self, info: str, error: str) -> None:
        """Create a repair issue for storage initialization failure."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="telegram_storage_error",
            translation_placeholders={
                "info": info,
                "error": error,
            },
        )

    async def stop(self) -> None:
        """Stop history store."""
        if self._async_remove_listener:
            self._async_remove_listener()
        if self.store is not None:
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
            timestamp=dt_util.parse_datetime(t["timestamp"]) or dt_util.now(),
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
        if self.store is None:
            return
        if (
            not isinstance(self.store, BufferedSqliteStore)
            or self.db_path == ":memory:"
        ):
            return

        history_store = Store[Any](
            self.hass, version=1, key="knx/telegrams_history.json"
        )
        try:
            json_data = await history_store.async_load()
            if json_data is None:
                return

            _LOGGER.info(
                "Migrating KNX telegram history from JSON to %s",
                self.store.__class__.__name__,
            )

            if not isinstance(json_data, list):
                _LOGGER.warning(
                    "Unexpected format in KNX telegram history JSON, skipping migration"
                )
                return

            stored_telegrams = [self.dict_to_model(t) for t in json_data]

            if stored_telegrams:
                await self.store.store_many(stored_telegrams)
                _LOGGER.info(
                    "Successfully migrated %d telegrams", len(stored_telegrams)
                )

            await history_store.async_remove()
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

    def _get_backend_info(self) -> str:
        """Get meaningful information about the current backend."""
        return self.db_path

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
