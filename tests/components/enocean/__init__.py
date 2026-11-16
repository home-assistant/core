"""Tests of the EnOcean integration."""

from collections.abc import Awaitable, Callable

from enocean_async.protocol.erp1.telegram import ERP1Telegram

type TelegramReceiver = Callable[[ERP1Telegram], Awaitable[None]]
