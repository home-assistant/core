"""Tests for Easywave device learning helpers."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.easywave.config_flow_learning import (
    EasywaveDeviceFlowMixin,
)
from homeassistant.components.easywave.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import LOCALE_EN, async_get_translations


class _LearningHelper(EasywaveDeviceFlowMixin):
    """Minimal mixin wrapper for learning helper tests."""


async def test_config_flow_translation_keys_exist(hass: HomeAssistant) -> None:
    """Verify strings used by the config flow resolve via the translation loader."""
    entity_translations = await async_get_translations(
        hass, LOCALE_EN, "entity", integrations=[DOMAIN]
    )
    selector_translations = await async_get_translations(
        hass, LOCALE_EN, "selector", integrations=[DOMAIN]
    )
    config_subentries_translations = await async_get_translations(
        hass,
        LOCALE_EN,
        "config_subentries",
        integrations=[DOMAIN],
        config_flow=True,
    )

    entity_prefix = f"component.{DOMAIN}.entity.sensor."
    assert (
        entity_translations[f"{entity_prefix}neo_sensor_temperature.name"]
        == "Temperature"
    )
    assert entity_translations[f"{entity_prefix}neo_sensor_humidity.name"] == "Humidity"
    assert (
        selector_translations[
            f"component.{DOMAIN}.selector.sensor_type.options.unknown"
        ]
        == "Unknown"
    )
    assert (
        config_subentries_translations[
            "component.easywave.config_subentries.easywave_transmitter.step.transmitter_learn_intro.title"
        ]
        == "Learn Transmitter"
    )
    assert (
        "component.easywave.config_subentries.easywave_neo_sensor.step.sensor_confirm.description"
        not in config_subentries_translations
    )


async def test_listen_for_telegram_resumes_after_suspend_failure() -> None:
    """Learning resumes telegram reception when suspending the listener fails."""
    helper = _LearningHelper()
    coordinator = MagicMock()
    coordinator.begin_learning = AsyncMock(return_value=True)
    coordinator.end_learning = MagicMock()
    coordinator.suspend_telegram_listener = AsyncMock(side_effect=OSError("usb busy"))
    coordinator.resume_telegram_listener = MagicMock()

    with pytest.raises(OSError, match="usb busy"):
        await helper._listen_for_telegram(
            coordinator, accept_telegram=lambda _telegram: None
        )

    coordinator.resume_telegram_listener.assert_called_once()
    coordinator.end_learning.assert_called_once()


async def test_listen_for_telegram_returns_none_when_learning_busy() -> None:
    """Learning aborts immediately when another session holds the lock."""
    helper = _LearningHelper()
    coordinator = MagicMock()
    coordinator.begin_learning = AsyncMock(return_value=False)
    coordinator.suspend_telegram_listener = AsyncMock()

    result = await helper._listen_for_telegram(
        coordinator, accept_telegram=lambda _telegram: None
    )

    assert result is None
    coordinator.suspend_telegram_listener.assert_not_called()


async def test_await_learning_task_uses_entry_background_task(
    hass: HomeAssistant,
) -> None:
    """Device learning is owned by the config entry so unload cancels it."""
    helper = _LearningHelper()
    helper.hass = hass
    entry = MagicMock()
    started = asyncio.Event()
    release = asyncio.Event()

    async def _learning(_coordinator: object) -> dict[str, object] | None:
        started.set()
        await release.wait()
        return {"serial": "aa"}

    def _create_background_task(
        _hass: HomeAssistant,
        coro: object,
        name: str,
        eager_start: bool = True,
    ) -> asyncio.Task[Any]:
        return hass.async_create_background_task(coro, name, eager_start)  # type: ignore[arg-type]

    entry.async_create_background_task = MagicMock(side_effect=_create_background_task)
    helper._get_entry = MagicMock(return_value=entry)  # type: ignore[method-assign]
    helper._get_coordinator = MagicMock(  # type: ignore[method-assign]
        return_value=MagicMock(
            transceiver=MagicMock(is_connected=True),
            is_learning_busy=MagicMock(return_value=False),
        )
    )
    helper._init_device_flow()
    helper._do_learning = _learning  # type: ignore[method-assign]
    helper.async_show_progress = MagicMock(  # type: ignore[method-assign]
        return_value={"type": "progress"}
    )
    helper.async_abort = MagicMock(return_value={"type": "abort"})  # type: ignore[method-assign]

    result = await helper._await_learning_task(
        progress_action="learn",
        confirm_step="confirm",
        learn_step="learn",
    )

    await asyncio.wait_for(started.wait(), timeout=1)
    entry.async_create_background_task.assert_called_once()
    assert (
        entry.async_create_background_task.call_args.args[2]
        == "easywave_device_learning"
    )
    assert result == {"type": "progress"}
    assert helper._learn_task is not None
    assert not helper._learn_task.done()
    release.set()
    await helper._learn_task
