"""Tests for the Beatbot coordinator."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from beatbot_cloud import (
    BeatbotAuthenticationError,
    BeatbotConnectionError,
    BeatbotDeviceData,
    BeatbotEvent,
)
import pytest

from homeassistant.components.beatbot import coordinator as coord_mod
from homeassistant.components.beatbot.coordinator import BeatbotCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

SUPPORTED_PRODUCT = "sblekiy3t188s9ql"


def _entry() -> SimpleNamespace:
    return SimpleNamespace(
        entry_id="entry",
        pref_disable_polling=False,
        async_on_unload=Mock(),
    )


def _device(device_id: str, product_id: str) -> BeatbotDeviceData:
    return BeatbotDeviceData(
        device_id=device_id,
        product_id=product_id,
        product_category="pool_clean_bot",
        work_status=0,
        work_mode=0,
        error_code=0,
        battery_level=80,
        versions=[],
        is_online=True,
    )


async def test_coordinator_keeps_all_pool_cleaners(hass: HomeAssistant) -> None:
    """Keep pool cleaners without restricting their product identifiers."""
    supported = _device("dev-supported", SUPPORTED_PRODUCT)
    newly_released = _device("dev-new", "new-product-id")
    api = SimpleNamespace(
        get_devices=AsyncMock(return_value=[supported, newly_released]),
        get_device_states=AsyncMock(return_value={}),
    )
    coordinator = BeatbotCoordinator(hass, api, _entry())

    data = await coordinator._async_update_data()

    assert data == {"dev-supported": supported, "dev-new": newly_released}
    api.get_device_states.assert_awaited_once()


async def test_coordinator_drops_unsupported_product_category(
    hass: HomeAssistant,
) -> None:
    """Devices outside the supported product categories are dropped."""
    device = _device("dev-mower", SUPPORTED_PRODUCT)
    device.product_category = "lawn_mower"
    api = SimpleNamespace(
        get_devices=AsyncMock(return_value=[device]),
        get_device_states=AsyncMock(return_value={}),
    )
    coordinator = BeatbotCoordinator(hass, api, _entry())

    data = await coordinator._async_update_data()

    assert data == {}
    api.get_device_states.assert_awaited_once()


async def test_coordinator_auth_failure_requests_reauth(
    hass: HomeAssistant,
) -> None:
    """Auth failures during first refresh become ConfigEntryAuthFailed."""
    api = SimpleNamespace(
        get_devices=AsyncMock(side_effect=BeatbotAuthenticationError),
        get_device_states=AsyncMock(return_value={}),
    )
    coordinator = BeatbotCoordinator(hass, api, _entry())

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_connection_failure_is_retryable(
    hass: HomeAssistant,
) -> None:
    """Connection failures during first refresh remain retryable setup failures."""
    api = SimpleNamespace(
        get_devices=AsyncMock(side_effect=BeatbotConnectionError),
        get_device_states=AsyncMock(return_value={}),
    )
    coordinator = BeatbotCoordinator(hass, api, _entry())

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_state_auth_failure_requests_reauth(
    hass: HomeAssistant,
) -> None:
    """Authentication failures from the state endpoint trigger reauth."""
    device = _device("dev-1", SUPPORTED_PRODUCT)
    api = SimpleNamespace(
        get_devices=AsyncMock(return_value=[device]),
        get_device_states=AsyncMock(side_effect=BeatbotAuthenticationError),
    )
    coordinator = BeatbotCoordinator(hass, api, _entry())

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_state_connection_failure_is_retryable(
    hass: HomeAssistant,
) -> None:
    """Fail the update when current runtime state cannot be fetched."""
    device = _device("dev-1", SUPPORTED_PRODUCT)
    api = SimpleNamespace(
        get_devices=AsyncMock(return_value=[device]),
        get_device_states=AsyncMock(side_effect=BeatbotConnectionError("offline")),
    )
    coordinator = BeatbotCoordinator(hass, api, _entry())

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_applies_batch_device_state(
    hass: HomeAssistant,
) -> None:
    """Apply runtime values returned by the batch state endpoint."""
    device = _device("dev-1", SUPPORTED_PRODUCT)
    api = SimpleNamespace(
        get_devices=AsyncMock(return_value=[device]),
        get_device_states=AsyncMock(
            return_value={
                "dev-1": {
                    "states": {"vacuum.battery": 42},
                    "is_online": False,
                }
            }
        ),
    )
    coordinator = BeatbotCoordinator(hass, api, _entry())

    data = await coordinator._async_update_data()

    assert data["dev-1"].battery_level == 42
    assert data["dev-1"].is_online is False


async def test_device_event_overlays_state_without_resetting_poll(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A push updates the existing device and only notifies listeners."""
    coordinator = BeatbotCoordinator(hass, SimpleNamespace(), _entry())
    device = _device("dev-1", SUPPORTED_PRODUCT)
    coordinator.async_set_updated_data({"dev-1": device})
    listener = Mock()
    remove_listener = coordinator.async_add_listener(listener)
    next_poll = coordinator._unsub_refresh
    coordinator.last_update_success = False

    with caplog.at_level(
        logging.DEBUG, logger="homeassistant.components.beatbot.coordinator"
    ):
        coordinator.async_apply_device_event(
            BeatbotEvent(
                "event-1",
                "properties_changed",
                "dev-1",
                {"interfaceInfo": "vacuum.battery", "value": 42},
            )
        )

    assert device.battery_level == 42
    assert device.is_online
    assert "Applied Beatbot state event" in caplog.text
    assert coordinator.last_update_success
    assert coordinator._unsub_refresh is next_poll
    listener.assert_called_once()
    remove_listener()


async def test_device_event_ignores_unknown_device(hass: HomeAssistant) -> None:
    """Ignore push events for devices outside coordinator data."""
    coordinator = BeatbotCoordinator(hass, SimpleNamespace(), _entry())
    coordinator.async_set_updated_data({})

    coordinator.async_apply_device_event(
        BeatbotEvent(
            "event-1",
            "properties_changed",
            "unknown",
            {"interfaceInfo": "vacuum.battery", "value": 42},
        )
    )

    assert coordinator.data == {}


async def test_device_event_ignores_non_state_event(hass: HomeAssistant) -> None:
    """Ignore topology events in the state coordinator."""
    device = _device("dev-1", SUPPORTED_PRODUCT)
    coordinator = BeatbotCoordinator(hass, SimpleNamespace(), _entry())
    coordinator.async_set_updated_data({"dev-1": device})

    coordinator.async_apply_device_event(
        BeatbotEvent("event-1", "device_added", "dev-1", {"deviceId": "dev-1"})
    )

    assert coordinator.data == {"dev-1": device}


async def test_poll_keeps_device_until_three_successful_discovery_misses(
    hass: HomeAssistant,
) -> None:
    """Keep a missing device until three successful discovery misses."""
    device = _device("dev-1", SUPPORTED_PRODUCT)
    api = SimpleNamespace(
        get_devices=AsyncMock(return_value=[]),
        get_device_states=AsyncMock(return_value={}),
    )
    coordinator = BeatbotCoordinator(hass, api, _entry())
    coordinator.async_set_updated_data({"dev-1": device})
    coordinator._remove_device_from_registries = Mock()
    coordinator._schedule_entry_reload = Mock()

    first = await coordinator._async_update_data()
    second = await coordinator._async_update_data()

    assert first == {"dev-1": device}
    assert second == {"dev-1": device}
    coordinator._remove_device_from_registries.assert_not_called()
    coordinator._schedule_entry_reload.assert_not_called()

    third = await coordinator._async_update_data()

    assert third == {"dev-1": device}
    coordinator._remove_device_from_registries.assert_called_once_with("dev-1")
    coordinator._schedule_entry_reload.assert_called_once()


async def test_poll_missing_counter_resets_when_device_returns(
    hass: HomeAssistant,
) -> None:
    """Reset the missing counter when a device returns."""
    device = _device("dev-1", SUPPORTED_PRODUCT)
    api = SimpleNamespace(
        get_devices=AsyncMock(side_effect=[[], [device], [], []]),
        get_device_states=AsyncMock(return_value={}),
    )
    coordinator = BeatbotCoordinator(hass, api, _entry())
    coordinator.async_set_updated_data({"dev-1": device})
    coordinator._remove_device_from_registries = Mock()
    coordinator._schedule_entry_reload = Mock()

    for _ in range(4):
        await coordinator._async_update_data()

    coordinator._remove_device_from_registries.assert_not_called()
    coordinator._schedule_entry_reload.assert_not_called()


async def test_poll_new_device_schedules_platform_reload(
    hass: HomeAssistant,
) -> None:
    """Reload platforms when discovery finds a new device."""
    device = _device("dev-new", SUPPORTED_PRODUCT)
    api = SimpleNamespace(
        get_devices=AsyncMock(return_value=[device]),
        get_device_states=AsyncMock(return_value={}),
    )
    coordinator = BeatbotCoordinator(hass, api, _entry())
    coordinator.async_set_updated_data({})
    coordinator._schedule_entry_reload = Mock()

    data = await coordinator._async_update_data()

    assert data == {"dev-new": device}
    coordinator._schedule_entry_reload.assert_called_once()


def test_entry_reload_is_scheduled_once(hass: HomeAssistant) -> None:
    """Use the config-entry scheduler and coalesce topology reloads."""
    hass.config_entries.async_schedule_reload = Mock()
    coordinator = BeatbotCoordinator(hass, SimpleNamespace(), _entry())

    coordinator._schedule_entry_reload()
    coordinator._schedule_entry_reload()

    hass.config_entries.async_schedule_reload.assert_called_once_with("entry")


async def test_poll_preserves_state_missing_from_batch(hass: HomeAssistant) -> None:
    """Preserve last-known runtime state when batch data omits a device."""
    previous = _device("dev-1", SUPPORTED_PRODUCT)
    previous.battery_level = 42
    discovered = _device("dev-1", SUPPORTED_PRODUCT)
    discovered.name = "Updated name"
    api = SimpleNamespace(
        get_devices=AsyncMock(return_value=[discovered]),
        get_device_states=AsyncMock(return_value={}),
    )
    coordinator = BeatbotCoordinator(hass, api, _entry())
    coordinator.async_set_updated_data({"dev-1": previous})

    data = await coordinator._async_update_data()

    assert data["dev-1"].name == "Updated name"
    assert data["dev-1"].battery_level == 42


async def test_poll_preserves_state_missing_from_partial_batch(
    hass: HomeAssistant,
) -> None:
    """Overlay partial batch data without resetting last-known runtime fields."""
    previous = _device("dev-1", SUPPORTED_PRODUCT)
    previous.work_status = 5
    previous.battery_level = 42
    discovered = _device("dev-1", SUPPORTED_PRODUCT)
    api = SimpleNamespace(
        get_devices=AsyncMock(return_value=[discovered]),
        get_device_states=AsyncMock(
            return_value={"dev-1": {"states": {"vacuum.battery": 75}}}
        ),
    )
    coordinator = BeatbotCoordinator(hass, api, _entry())
    coordinator.async_set_updated_data({"dev-1": previous})

    data = await coordinator._async_update_data()

    assert data["dev-1"].work_status == 5
    assert data["dev-1"].battery_level == 75
    assert data["dev-1"].is_online is True


async def test_poll_removes_registry_only_stale_device_after_three_misses(
    hass: HomeAssistant,
) -> None:
    """Remove a registry-only device after three discovery misses."""
    api = SimpleNamespace(
        get_devices=AsyncMock(return_value=[]),
        get_device_states=AsyncMock(return_value={}),
    )
    coordinator = BeatbotCoordinator(hass, api, _entry())
    coordinator.async_set_updated_data({})
    coordinator._registered_device_ids = Mock(return_value={"dev-stale"})
    coordinator._remove_device_from_registries = Mock()
    coordinator._schedule_entry_reload = Mock()

    await coordinator._async_update_data()
    await coordinator._async_update_data()
    coordinator._remove_device_from_registries.assert_not_called()

    await coordinator._async_update_data()

    coordinator._remove_device_from_registries.assert_called_once_with("dev-stale")
    coordinator._schedule_entry_reload.assert_called_once()


def test_coordinator_finds_and_removes_registered_device(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Find Beatbot identifiers and remove their matching registry entities."""
    registry_device = SimpleNamespace(
        id="registry-device-id",
        identifiers={(coord_mod.DOMAIN, "dev-1"), ("other", "ignored")},
    )
    device_registry = SimpleNamespace(
        async_get_device_by_identifier=Mock(return_value=registry_device),
        async_update_device=Mock(),
    )
    entity_registry = SimpleNamespace(async_remove=Mock())
    monkeypatch.setattr(coord_mod.dr, "async_get", Mock(return_value=device_registry))
    monkeypatch.setattr(
        coord_mod.dr,
        "async_entries_for_config_entry",
        Mock(return_value=[registry_device]),
    )
    monkeypatch.setattr(coord_mod.er, "async_get", Mock(return_value=entity_registry))
    monkeypatch.setattr(
        coord_mod.er,
        "async_entries_for_device",
        Mock(
            return_value=[
                SimpleNamespace(config_entry_id="entry", entity_id="sensor.beatbot"),
                SimpleNamespace(config_entry_id="other", entity_id="sensor.other"),
            ]
        ),
    )
    coordinator = BeatbotCoordinator(hass, SimpleNamespace(), _entry())

    assert coordinator._registered_device_ids() == {"dev-1"}

    coordinator._remove_device_from_registries("dev-1")

    device_registry.async_get_device_by_identifier.assert_called_once_with(
        (coord_mod.DOMAIN, "dev-1"), "entry"
    )
    entity_registry.async_remove.assert_called_once_with("sensor.beatbot")
    device_registry.async_update_device.assert_called_once_with(
        "registry-device-id", remove_config_entry_id="entry"
    )


def test_remove_missing_registry_device(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ignore removal when no registry device exists."""
    device_registry = SimpleNamespace(
        async_get_device_by_identifier=Mock(return_value=None)
    )
    monkeypatch.setattr(coord_mod.dr, "async_get", Mock(return_value=device_registry))
    coordinator = BeatbotCoordinator(hass, SimpleNamespace(), _entry())

    coordinator._remove_device_from_registries("missing")

    device_registry.async_get_device_by_identifier.assert_called_once_with(
        (coord_mod.DOMAIN, "missing"), "entry"
    )
