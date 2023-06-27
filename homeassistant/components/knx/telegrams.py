"""KNX Telegram handler."""
from __future__ import annotations

from collections import deque
from collections.abc import Callable
import datetime as dt
from typing import TypedDict

from xknx import XKNX
from xknx.exceptions import XKNXException
from xknx.telegram import Telegram
from xknx.telegram.apci import GroupValueResponse, GroupValueWrite

from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
import homeassistant.util.dt as dt_util

from .project import KNXProject


class TelegramDict(TypedDict):
    """Represent a Telegram as a dict."""

    # this has to be in sync with the frontend implementation
    destination: str
    destination_name: str
    direction: str
    dpt_main: int | None
    dpt_sub: int | None
    dpt_name: str | None
    payload: int | tuple[int, ...] | None
    source: str
    source_name: str
    telegramtype: str
    timestamp: dt.datetime
    unit: str | None
    value: str | int | float | bool | None


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
        self._jobs: list[HassJob[[TelegramDict], None]] = []
        self._xknx_telegram_cb_handle = (
            xknx.telegram_queue.register_telegram_received_cb(
                telegram_received_cb=self._xknx_telegram_cb,
                match_for_outgoing=True,
            )
        )
        self.recent_telegrams: deque[TelegramDict] = deque(maxlen=log_size)

    async def _xknx_telegram_cb(self, telegram: Telegram) -> None:
        """Handle incoming and outgoing telegrams from xknx."""
        telegram_dict = self.telegram_to_dict(telegram)
        self.recent_telegrams.append(telegram_dict)
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
        dpt_main = None
        dpt_sub = None
        dpt_name = None
        payload_data: int | tuple[int, ...] | None = None
        src_name = ""
        transcoder = None
        unit = None
        value: str | int | float | bool | None = None

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
                try:
                    value = transcoder.from_knx(telegram.payload.value)
                    dpt_main = transcoder.dpt_main_number
                    dpt_sub = transcoder.dpt_sub_number
                    dpt_name = transcoder.value_type
                    unit = transcoder.unit
                except XKNXException:
                    value = "Error decoding value"

        return TelegramDict(
            destination=f"{telegram.destination_address}",
            destination_name=dst_name,
            direction=telegram.direction.value,
            dpt_main=dpt_main,
            dpt_sub=dpt_sub,
            dpt_name=dpt_name,
            payload=payload_data,
            source=f"{telegram.source_address}",
            source_name=src_name,
            telegramtype=telegram.payload.__class__.__name__,
            timestamp=dt_util.as_local(dt_util.utcnow()),
            unit=unit,
            value=value,
        )
