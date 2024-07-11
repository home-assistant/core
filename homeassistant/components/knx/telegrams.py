"""KNX Telegram handler."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Final, TypedDict

from xknx import XKNX
from xknx.dpt import DPTArray, DPTBase, DPTBinary
from xknx.exceptions import XKNXException
from xknx.telegram import Telegram
from xknx.telegram.apci import GroupValueResponse, GroupValueWrite

from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
import homeassistant.util.dt as dt_util
from homeassistant.util.signal_type import SignalType

from .const import DOMAIN
from .project import KNXProject

STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}/telegrams_history.json"

# dispatcher signal for KNX interface device triggers
SIGNAL_KNX_TELEGRAM: SignalType[Telegram, TelegramDict] = SignalType("knx_telegram")


class DecodedTelegramPayload(TypedDict):
    """Decoded payload value and metadata."""

    dpt_main: int | None
    dpt_sub: int | None
    dpt_name: str | None
    unit: str | None
    value: str | int | float | bool | None


class TelegramDict(DecodedTelegramPayload):
    """Represent a Telegram as a dict."""

    # this has to be in sync with the frontend implementation
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
        log_size: int,
    ) -> None:
        """Initialize Telegrams class."""
        self.hass = hass
        self.project = project
        self._history_store = Store[list[TelegramDict]](
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        self._jobs: list[HassJob[[TelegramDict], None]] = []
        self._xknx_telegram_cb_handle = (
            xknx.telegram_queue.register_telegram_received_cb(
                telegram_received_cb=self._xknx_telegram_cb,
                match_for_outgoing=True,
            )
        )
        self.recent_telegrams: deque[TelegramDict] = deque(maxlen=log_size)

    async def load_history(self) -> None:
        """Load history from store."""
        if (telegrams := await self._history_store.async_load()) is None:
            return
        if self.recent_telegrams.maxlen == 0:
            await self._history_store.async_remove()
            return
        for telegram in telegrams:
            # tuples are stored as lists in JSON
            if isinstance(telegram["payload"], list):
                telegram["payload"] = tuple(telegram["payload"])  # type: ignore[unreachable]
        self.recent_telegrams.extend(telegrams)

    async def save_history(self) -> None:
        """Save history to store."""
        if self.recent_telegrams:
            await self._history_store.async_save(list(self.recent_telegrams))

    async def _xknx_telegram_cb(self, telegram: Telegram) -> None:
        """Handle incoming and outgoing telegrams from xknx."""
        telegram_dict = self.telegram_to_dict(telegram)
        self.recent_telegrams.append(telegram_dict)
        async_dispatcher_send(self.hass, SIGNAL_KNX_TELEGRAM, telegram, telegram_dict)
        for job in self._jobs:
            self.hass.async_run_hass_job(job, telegram_dict)

    @callback
    def async_listen_telegram(
        self,
        action: Callable[[TelegramDict], None],
        name: str = "KNX telegram listener",
    ) -> CALLBACK_TYPE:
        """Register callback to listen for telegrams."""
        job = HassJob(action, name=name)
        self._jobs.append(job)

        def remove_listener() -> None:
            """Remove the listener."""
            self._jobs.remove(job)

        return remove_listener

    def telegram_to_dict(self, telegram: Telegram) -> TelegramDict:
        """Convert a Telegram to a dict."""
        dst_name = ""
        payload_data: int | tuple[int, ...] | None = None
        src_name = ""
        transcoder = None
        decoded_payload: DecodedTelegramPayload | None = None

        if (
            ga_info := self.project.group_addresses.get(
                f"{telegram.destination_address}"
            )
        ) is not None:
            dst_name = ga_info.name
            transcoder = ga_info.transcoder

        if (
            device := self.project.devices.get(f"{telegram.source_address}")
        ) is not None:
            src_name = f"{device['manufacturer_name']} {device['name']}"

        if isinstance(telegram.payload, (GroupValueWrite, GroupValueResponse)):
            payload_data = telegram.payload.value.value
            if transcoder is not None:
                decoded_payload = decode_telegram_payload(
                    payload=telegram.payload.value, transcoder=transcoder
                )

        return TelegramDict(
            destination=f"{telegram.destination_address}",
            destination_name=dst_name,
            direction=telegram.direction.value,
            dpt_main=decoded_payload["dpt_main"]
            if decoded_payload is not None
            else None,
            dpt_sub=decoded_payload["dpt_sub"] if decoded_payload is not None else None,
            dpt_name=decoded_payload["dpt_name"]
            if decoded_payload is not None
            else None,
            payload=payload_data,
            source=f"{telegram.source_address}",
            source_name=src_name,
            telegramtype=telegram.payload.__class__.__name__,
            timestamp=dt_util.now().isoformat(),
            unit=decoded_payload["unit"] if decoded_payload is not None else None,
            value=decoded_payload["value"] if decoded_payload is not None else None,
        )


def decode_telegram_payload(
    payload: DPTArray | DPTBinary, transcoder: type[DPTBase]
) -> DecodedTelegramPayload:
    """Decode the payload of a KNX telegram."""
    try:
        value = transcoder.from_knx(payload)
    except XKNXException:
        value = "Error decoding value"

    return DecodedTelegramPayload(
        dpt_main=transcoder.dpt_main_number,
        dpt_sub=transcoder.dpt_sub_number,
        dpt_name=transcoder.value_type,
        unit=transcoder.unit,
        value=value,
    )
