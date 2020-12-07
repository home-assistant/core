"""Test the HarmonySubscriberMixin class."""

import asyncio

from homeassistant.components.harmony.subscriber import (
    HarmonyCallback,
    HarmonySubscriberMixin,
)

from tests.async_mock import AsyncMock, MagicMock

_NO_PARAM_CALLBACKS = {
    "connected": "_connected",
    "disconnected": "_disconnected",
    "config_updated": "_config_updated",
}

_ACTIVITY_CALLBACKS = {
    "activity_starting": "_activity_starting",
    "activity_started": "_activity_started",
}

_ALL_CALLBACK_NAMES = list(_NO_PARAM_CALLBACKS.keys()) + list(
    _ACTIVITY_CALLBACKS.keys()
)

_ACTIVITY_TUPLE = ("not", "used")


async def test_no_callbacks():
    """Ensure we handle no subscriptions."""
    subscriber = HarmonySubscriberMixin()
    _call_all_callbacks(subscriber)


async def test_empty_callbacks():
    """Ensure we handle a missing callback in a subscription."""
    subscriber = HarmonySubscriberMixin()

    callbacks = {k: None for k in _ALL_CALLBACK_NAMES}
    subscriber.async_subscribe(HarmonyCallback(**callbacks))
    _call_all_callbacks(subscriber)


async def test_async_callbacks():
    """Ensure we handle async callbacks."""
    subscriber = HarmonySubscriberMixin()

    callbacks = {k: AsyncMock() for k in _ALL_CALLBACK_NAMES}
    subscriber.async_subscribe(HarmonyCallback(**callbacks))
    _call_all_callbacks(subscriber)
    await asyncio.sleep(0)

    for callback_name in _NO_PARAM_CALLBACKS.keys():
        callback_mock = callbacks[callback_name]
        callback_mock.assert_awaited_once()

    for callback_name in _ACTIVITY_CALLBACKS.keys():
        callback_mock = callbacks[callback_name]
        callback_mock.assert_awaited_once_with(_ACTIVITY_TUPLE)


async def test_callbacks():
    """Ensure we handle non-async callbacks."""
    subscriber = HarmonySubscriberMixin()

    callbacks = {k: MagicMock() for k in _ALL_CALLBACK_NAMES}
    subscriber.async_subscribe(HarmonyCallback(**callbacks))
    _call_all_callbacks(subscriber)

    for callback_name in _NO_PARAM_CALLBACKS.keys():
        callback_mock = callbacks[callback_name]
        callback_mock.assert_called_once()

    for callback_name in _ACTIVITY_CALLBACKS.keys():
        callback_mock = callbacks[callback_name]
        callback_mock.assert_called_once_with(_ACTIVITY_TUPLE)


def _call_all_callbacks(subscriber):
    for callback_method in _NO_PARAM_CALLBACKS.values():
        to_call = getattr(subscriber, callback_method)
        to_call()

    for callback_method in _ACTIVITY_CALLBACKS.values():
        to_call = getattr(subscriber, callback_method)
        to_call(_ACTIVITY_TUPLE)
