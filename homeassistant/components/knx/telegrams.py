"""KNX Telegram handler."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable, Mapping
from datetime import datetime
import logging
import re
from typing import Any, TypedDict

from knx_telegram_store import StoredTelegram, TelegramStore
from knx_telegram_store.backends.memory import MemoryStore
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
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.util import dt as dt_util
from homeassistant.util.signal_type import SignalType

from .const import (
    CONF_KNX_TELEGRAM_BACKEND,
    CONF_KNX_TELEGRAM_DB_PATH,
    CONF_KNX_TELEGRAM_DSN,
    CONF_KNX_TELEGRAM_LOG_SIZE,
    CONF_KNX_TELEGRAM_RETENTION_DAYS,
    DOMAIN,
    REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR,
    TELEGRAM_BACKEND_MEMORY,
    TELEGRAM_BACKEND_POSTGRES,
    TELEGRAM_BACKEND_SQLITE,
    TELEGRAM_DB_PATH_DEFAULT,
    TELEGRAM_LOG_DEFAULT,
    TELEGRAM_RETENTION_DEFAULT,
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

        backend = config.get(CONF_KNX_TELEGRAM_BACKEND, TELEGRAM_BACKEND_MEMORY)
        self.store: TelegramStore

        if backend == TELEGRAM_BACKEND_POSTGRES:
            dsn = str(config.get(CONF_KNX_TELEGRAM_DSN, ""))
            if dsn:
                # Fix potential float port in DSN (e.g. :5432.0/)
                dsn = re.sub(r":(\d+)\.0($|[/?])", r":\1\2", dsn)
            retention = config.get(
                CONF_KNX_TELEGRAM_RETENTION_DAYS, TELEGRAM_RETENTION_DEFAULT
            )
            self.store = PostgresStore(dsn, retention_days=retention)
        elif backend == TELEGRAM_BACKEND_SQLITE:
            db_path = str(
                config.get(CONF_KNX_TELEGRAM_DB_PATH, TELEGRAM_DB_PATH_DEFAULT)
            )
            full_path = (
                db_path
                if db_path == ":memory:"
                else hass.config.path(STORAGE_DIR, db_path)
            )
            retention = config.get(
                CONF_KNX_TELEGRAM_RETENTION_DAYS, TELEGRAM_RETENTION_DEFAULT
            )
            self.store = SqliteStore(full_path, retention_days=retention)
        else:  # Memory
            log_size = config.get(CONF_KNX_TELEGRAM_LOG_SIZE, TELEGRAM_LOG_DEFAULT)
            self.store = MemoryStore(max_telegrams=log_size)

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
        self.recent_telegrams: deque[TelegramDict] = deque(
            maxlen=config.get(CONF_KNX_TELEGRAM_LOG_SIZE, TELEGRAM_LOG_DEFAULT)
        )
        self.last_ga_telegrams: dict[str, TelegramDict] = {}
        self._async_remove_listener: Callable[[], None] | None = None

    async def load_history(self) -> None:
        """Load history from store."""
        backend = self.config.get(CONF_KNX_TELEGRAM_BACKEND, TELEGRAM_BACKEND_MEMORY)
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
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Error initializing KNX telegram storage backend '%s' (%s): %s",
                backend,
                info,
                err,
            )
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                REPAIR_ISSUE_TELEGRAM_BACKEND_ERROR,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="telegram_storage_error",
            )
            # Detailed persistent notification for immediate feedback
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "KNX Telegram Storage Error",
                        "message": (
                            f"The configured KNX telegram storage backend '{backend}' failed to initialize. "
                            "Home Assistant has fallen back to memory-only storage. "
                            "Telegram history will be lost on restart until the issue is resolved.\n\n"
                            f"**Configuration**: `{info}`\n"
                            f"**Error**: {err}"
                        ),
                        "notification_id": "knx_telegram_backend_error",
                    },
                )
            )
            # Fallback to MemoryStore to allow integration to start
            if not isinstance(self.store, MemoryStore):
                log_size = self.config.get(
                    CONF_KNX_TELEGRAM_LOG_SIZE, TELEGRAM_LOG_DEFAULT
                )
                self.store = MemoryStore(max_telegrams=log_size)
                await self.store.initialize()

        # Initial eviction for SQL backends
        await self.store.evict_expired()

        # Schedule nightly eviction at 3:00 AM
        self._async_remove_listener = async_track_utc_time_change(
            self.hass, self._async_evict_telegrams, hour=3, minute=0, second=0
        )

    async def stop(self) -> None:
        """Stop history store."""
        if self._async_remove_listener:
            self._async_remove_listener()
        await self.store.close()

    async def _async_evict_telegrams(self, _now: datetime) -> None:
        """Evict expired telegrams from store."""
        _LOGGER.debug("Starting nightly KNX telegram eviction")
        count = await self.store.evict_expired()
        if count > 0:
            _LOGGER.info("Evicted %d expired KNX telegrams", count)

    def _xknx_telegram_cb(self, telegram: Telegram) -> None:
        """Handle incoming and outgoing telegrams from xknx."""
        telegram_dict = self.telegram_to_dict(telegram)
        self.recent_telegrams.append(telegram_dict)
        if telegram_dict["payload"] is not None:
            # exclude GroupValueRead telegrams
            self.last_ga_telegrams[telegram_dict["destination"]] = telegram_dict

        # Store in history store asynchronously
        if self.recent_telegrams.maxlen != 0:
            self.hass.async_create_task(
                self.store.store(self.dict_to_model(telegram_dict))
            )

        async_dispatcher_send(self.hass, SIGNAL_KNX_TELEGRAM, telegram, telegram_dict)

    def _xknx_data_secure_group_key_issue_cb(self, telegram: Telegram) -> None:
        """Handle telegrams with undecodable data secure payload from xknx."""
        telegram_dict = self.telegram_to_dict(telegram)
        self.recent_telegrams.append(telegram_dict)

        # Store in history store asynchronously
        if self.recent_telegrams.maxlen != 0:
            self.hass.async_create_task(
                self.store.store(self.dict_to_model(telegram_dict))
            )

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
        return StoredTelegram(
            timestamp=dt_util.parse_datetime(t["timestamp"]) or dt_util.now(),
            source=t["source"],
            destination=t["destination"],
            direction=t["direction"],
            telegramtype=t["telegramtype"],
            payload=t["payload"],
            value=t["value"] if isinstance(t["value"], (int, float, bool)) else None,
            dpt_main=t["dpt_main"],
            dpt_sub=t["dpt_sub"],
            unit=t["unit"],
            source_name=t["source_name"],
            destination_name=t["destination_name"],
            data_secure=t["data_secure"],
        )

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
            dpt_name=None,  # Not stored, could be resolved if needed
            unit=m.unit,
            source_name=m.source_name,
            destination_name=m.destination_name,
            data_secure=m.data_secure,
        )

    def _get_backend_info(self) -> str:
        """Get meaningful information about the current backend."""
        backend = self.config.get(CONF_KNX_TELEGRAM_BACKEND, TELEGRAM_BACKEND_MEMORY)
        if backend == TELEGRAM_BACKEND_POSTGRES:
            dsn = self.config.get(CONF_KNX_TELEGRAM_DSN, "")
            # Mask password
            dsn = re.sub(r":([^/@]+)@", r":****@", dsn)
            # Fix potential float port (e.g. :5432.0/)
            return re.sub(r":(\d+)\.0($|[/?])", r":\1\2", dsn)
        if backend == TELEGRAM_BACKEND_SQLITE:
            return str(
                self.config.get(CONF_KNX_TELEGRAM_DB_PATH, TELEGRAM_DB_PATH_DEFAULT)
            )
        return "Memory"


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
