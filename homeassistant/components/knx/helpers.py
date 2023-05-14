"""Helper functions for KNX."""
from __future__ import annotations

from typing import TypedDict

from xknx.exceptions import XKNXException
from xknx.telegram import Telegram
from xknx.telegram.apci import GroupValueResponse, GroupValueWrite

from .project import KNXProject


class TelegramDict(TypedDict):
    """Represent a Telegram as a dict."""

    destination: str
    destination_name: str
    direction: str
    payload: int | tuple[int, ...] | None
    source: str
    source_name: str
    telegramtype: str
    value: str | int | float | bool | None


def telegram_to_dict(telegram: Telegram, project: KNXProject) -> TelegramDict:
    """Convert a Telegram to a dict."""
    dst_name = ""
    payload_data: int | tuple[int, ...] | None = None
    src_name = ""
    transcoder = None
    value: str | int | float | bool | None = None

    if (
        ga_info := project.group_addresses.get(f"{telegram.destination_address}")
    ) is not None:
        dst_name = ga_info.name
        transcoder = ga_info.transcoder

    if (device := project.devices.get(f"{telegram.source_address}")) is not None:
        src_name = device["name"]

    if isinstance(telegram.payload, (GroupValueWrite, GroupValueResponse)):
        payload_data = telegram.payload.value.value
        if transcoder is not None:
            try:
                value = transcoder.from_knx(telegram.payload.value)
            except XKNXException:
                value = None

    return TelegramDict(
        destination=f"{telegram.destination_address}",
        destination_name=dst_name,
        direction=telegram.direction.value,
        payload=payload_data,
        source=f"{telegram.source_address}",
        source_name=src_name,
        telegramtype=telegram.payload.__class__.__name__,
        value=value,
    )
