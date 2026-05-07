"""KNX Telegrams history and storage."""

import asyncio
from collections.abc import Callable, Mapping
import json
import logging
import os
import re
from typing import Any, TypedDict

from knx_telegram_store import StoredTelegram, TelegramQuery, TelegramStore
from knx_telegram_store.backends.postgres import PostgresStore
from knx_telegram_store.backends.sqlite import SqliteStore
from xknx import XKNX
from xknx.dpt import DPTArray, DPTBase, DPTBinary
from xknx.dpt.dpt import DPTComplexData, DPTEnumData
from xknx.exceptions import XKNXException
from xknx.telegram import Telegram, TelegramDirection
from xknx.telegram.apci import GroupValueResponse, GroupValueWrite

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.util import dt as dt_util
from homeassistant.util.signal_type import SignalType

from .const import (
    CONF_KNX_TELEGRAM_DB_BACKEND,
    CONF_KNX_TELEGRAM_DB_PATH,
    CONF_KNX_TELEGRAM_DSN,
    DOMAIN,
    REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR,
    TELEGRAM_BACKEND_POSTGRES,
    TELEGRAM_BACKEND_SQLITE,
    TELEGRAM_DB_PATH_DEFAULT,
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
        config: Mapping[str, Any],
    ) -> None:
        """Initialize Telegrams class."""
        self.hass = hass
        self.project = project
        self.config = config

        backend = config.get(CONF_KNX_TELEGRAM_DB_BACKEND, TELEGRAM_BACKEND_SQLITE)
        self.store: TelegramStore | None = None

        if backend == TELEGRAM_BACKEND_POSTGRES:
            dsn = str(config.get(CONF_KNX_TELEGRAM_DSN, ""))
            if dsn:
                # Fix potential float port in DSN (e.g. :5432.0/)
                dsn = re.sub(r":(\d+)\.0($|[/?])", r":\1\2", dsn)
            self.store = PostgresStore(dsn)
        elif backend == TELEGRAM_BACKEND_SQLITE:
            db_path = config.get(CONF_KNX_TELEGRAM_DB_PATH, TELEGRAM_DB_PATH_DEFAULT)
            full_path = (
                db_path
                if db_path == ":memory:"
                else hass.config.path(STORAGE_DIR, db_path)
            )
            self.store = SqliteStore(full_path)
        else:
            _LOGGER.error(
                "Invalid KNX telegram storage backend configured: %s", backend
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
        self._pending_tasks: set[asyncio.Task[Any]] = set()

    async def load_history(self) -> None:
        """Load history from store."""
        backend = self.config.get(CONF_KNX_TELEGRAM_DB_BACKEND, TELEGRAM_BACKEND_SQLITE)
        if self.store is None:
            return
        info = self._get_backend_info()
        try:
            _LOGGER.debug(
                "Initializing KNX telegram storage backend '%s' (%s)", backend, info
            )
            async with asyncio.timeout(10):
                await self.store.initialize()
            _LOGGER.info(
                "Successfully initialized KNX telegram storage backend '%s'", backend
            )
        except TimeoutError:
            _LOGGER.error(
                "Timeout initializing KNX telegram storage backend '%s' (%s)",
                backend,
                info,
            )
            self._create_repair_issue(backend, info, "Timeout")
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Error initializing KNX telegram storage backend '%s' (%s): %s",
                backend,
                info,
                err,
            )
            self._create_repair_issue(backend, info, str(err))
        else:
            ir.async_delete_issue(
                self.hass, DOMAIN, REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR
            )

        # Migrate legacy JSON storage if it exists
        await self.migrate_telegrams()

        # Hydrate last_ga_telegrams from store
        if self.store is not None:
            try:
                query = TelegramQuery(limit=1000, order_descending=False)
                result = await self.store.query(query)
                for m in result.telegrams:
                    t_dict = self.model_to_dict(m)
                    if t_dict["payload"] is not None:
                        self.last_ga_telegrams[t_dict["destination"]] = t_dict
                _LOGGER.debug("Hydrated %d telegrams from store", len(result.telegrams))
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Error hydrating last_ga_telegrams: %s", err)

    def _create_repair_issue(self, backend: str, info: str, error: str) -> None:
        """Create a repair issue for storage initialization failure."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="telegram_storage_error",
            translation_placeholders={
                "backend": backend,
                "info": info,
                "error": error,
            },
        )

    async def stop(self) -> None:
        """Stop history store."""
        if self._async_remove_listener:
            self._async_remove_listener()
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
        if self.store is not None:
            await self.store.close()

    def _xknx_telegram_cb(self, telegram: Telegram) -> None:
        """Handle incoming and outgoing telegrams from xknx."""
        telegram_dict = self.telegram_to_dict(telegram)
        if telegram_dict["payload"] is not None:
            # exclude GroupValueRead telegrams
            self.last_ga_telegrams[telegram_dict["destination"]] = telegram_dict

        # Store in history store asynchronously
        if self.store is not None:
            if len(self._pending_tasks) > 100:
                _LOGGER.warning("Too many pending telegram storage tasks, skipping")
                return
            task = self.hass.async_create_task(
                self.store.store(self.dict_to_model(telegram_dict))
            )
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)

        async_dispatcher_send(self.hass, SIGNAL_KNX_TELEGRAM, telegram, telegram_dict)

    def _xknx_data_secure_group_key_issue_cb(self, telegram: Telegram) -> None:
        """Handle telegrams with undecodable data secure payload from xknx."""
        telegram_dict = self.telegram_to_dict(telegram)

        # Store in history store asynchronously
        if self.store is not None:
            if len(self._pending_tasks) > 100:
                _LOGGER.warning("Too many pending telegram storage tasks, skipping")
                return
            task = self.hass.async_create_task(
                self.store.store(self.dict_to_model(telegram_dict))
            )
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)

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

        # Ensure value is a serializable type supported by the store
        # Supported: int, float, bool, str, dict (JSON)
        is_supported_type = isinstance(value, (int, float, bool, str, dict))
        store_value = value if is_supported_type else None

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
            value=store_value,
            value_numeric=value_numeric,
            dpt_main=t["dpt_main"],
            dpt_sub=t["dpt_sub"],
            unit=t["unit"],
            source_name=t["source_name"],
            destination_name=t["destination_name"],
            data_secure=t["data_secure"],
        )

    async def migrate_telegrams(self) -> None:
        """Migrate telegrams from JSON storage to the current store."""
        if (
            not isinstance(self.store, SqliteStore)
            or self.store.engine.url.database == ":memory:"
        ):
            return

        path = self.hass.config.path(STORAGE_DIR, "knx/telegrams_history.json")
        if not await self.hass.async_add_executor_job(os.path.exists, path):
            return

        _LOGGER.info(
            "Migrating KNX telegram history from JSON to %s",
            self.store.__class__.__name__,
        )
        try:

            def _load_json() -> dict[str, Any]:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)  # type: ignore[no-any-return]

            json_data = await self.hass.async_add_executor_job(_load_json)
            telegrams_data = json_data.get("data", [])

            stored_telegrams = [self.dict_to_model(t) for t in telegrams_data]

            if stored_telegrams:
                await self.store.store_many(stored_telegrams)
                _LOGGER.info(
                    "Successfully migrated %d telegrams", len(stored_telegrams)
                )

            await self.hass.async_add_executor_job(os.remove, path)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error migrating KNX telegram history: %s", err)

    def model_to_dict(self, m: StoredTelegram) -> TelegramDict:
        """Convert a StoredTelegram model to a TelegramDict."""
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
            dpt_name=self._resolve_dpt_name(m.dpt_main, m.dpt_sub),
            unit=m.unit,
            source_name=m.source_name,
            destination_name=m.destination_name,
            data_secure=m.data_secure,
        )

    def _get_backend_info(self) -> str:
        """Get meaningful information about the current backend."""
        backend = self.config.get(CONF_KNX_TELEGRAM_DB_BACKEND, TELEGRAM_BACKEND_SQLITE)
        if backend == TELEGRAM_BACKEND_POSTGRES:
            dsn = self.config.get(CONF_KNX_TELEGRAM_DSN, "")
            # Mask password
            dsn = re.sub(r":([^/@]+)@", r":****@", dsn)
            # Fix potential float port (e.g. :5432.0/)
            return re.sub(r":(\d+)\.0($|[/?])", r":\1\2", dsn)
        if backend == TELEGRAM_BACKEND_SQLITE:
            return TELEGRAM_DB_PATH_DEFAULT
        return "Unknown"

    def _resolve_dpt_name(self, main: int | None, sub: int | None) -> str | None:
        """Resolve DPT name from main and sub numbers."""
        if main is None or sub is None:
            return None
        try:
            if transcoder := DPTBase.parse_transcoder(f"{main}.{sub:03}"):
                return transcoder.value_type
        except Exception:  # noqa: BLE001
            pass
        return None


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
