"""Tests for BluettiDevice._handle_unbind and remaining BluettiData behavior."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.bluetti_cloud import BluettiRuntimeData
from homeassistant.components.bluetti_cloud.const import DOMAIN
from homeassistant.components.bluetti_cloud.models import BluettiData, BluettiDevice
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_web_socket_message_handler_schedules_coordinator_refresh(
    hass: HomeAssistant,
) -> None:
    """Web socket message handler schedules coordinator refresh."""
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L"
    )
    device.coordinator = MagicMock()
    # A plain MagicMock (not AsyncMock): run_coroutine_threadsafe is mocked
    # below too, so nothing actually awaits the "coroutine" it returns.
    device.coordinator.async_request_refresh = MagicMock()

    data = BluettiData.__new__(BluettiData)
    data.devices = [device]
    data.loop = asyncio.get_running_loop()

    with patch(
        "homeassistant.components.bluetti_cloud.models.asyncio.run_coroutine_threadsafe"
    ) as mock_run:
        data.web_socket_message_handler('{"data": {"deviceSn": "SN1"}}')

    mock_run.assert_called_once()


async def test_web_socket_message_handler_ignores_unknown_device(
    hass: HomeAssistant,
) -> None:
    """Web socket message handler ignores unknown device."""
    data = BluettiData.__new__(BluettiData)
    data.devices = []
    data.loop = asyncio.get_running_loop()

    with patch(
        "homeassistant.components.bluetti_cloud.models.asyncio.run_coroutine_threadsafe"
    ) as mock_run:
        data.web_socket_message_handler('{"data": {"deviceSn": "unknown"}}')

    mock_run.assert_not_called()


async def test_handle_unbind_without_hass_or_entry_returns_early(
    hass: HomeAssistant,
) -> None:
    """Handle unbind without hass or entry returns early, and stays retriable.

    Regression test: _unbind_processed used to be set unconditionally at the
    top of _handle_unbind(), before this early-return check - a transient
    setup-ordering issue (unbind detected before bind_runtime() wired _hass/
    _entry up) would then permanently suppress every later unbind attempt,
    even once those references become available, leaving the device
    configured forever despite the cloud continuing to report it unbound.
    """
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L"
    )
    # _hass and _entry default to None.

    await device._handle_unbind()

    assert device._unbind_processed is False


async def test_handle_unbind_full_cleanup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Handle unbind removes the device, its entities, and notifies - no persistence.

    Batteries-included means there is no per-entry device list to update
    here (see __init__.py's async_remove_config_entry_device) - this is
    pure live registry and runtime_data cleanup, so unlike the old
    persistence-gated version there is nothing to reload either.
    """
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test Device", sn="SN1", model="Balco260"
    )
    other_device = BluettiDevice(
        device_id="SN2", on_line="1", name="Other", sn="SN2", model="AC200L"
    )

    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "SN1")},
        name="Test Device",
        manufacturer="Bluetti",
        model="Balco260",
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "SN1_SOC",
        config_entry=entry,
        device_id=device_entry.id,
    )

    coordinator = AsyncMock()
    entry.runtime_data = BluettiRuntimeData(
        bluetti_devices=MagicMock(devices=[device, other_device]),
        stomp_client=MagicMock(),
        coordinators={"SN1": coordinator, "SN2": MagicMock()},
    )

    device._hass = hass
    device._entry = entry
    device._entry_id = entry.entry_id

    with patch(
        "homeassistant.components.bluetti_cloud.models.persistent_notification.async_create"
    ) as mock_notify:
        await device._handle_unbind()
        await hass.async_block_till_done()

    # Device + its entities removed from the registries.
    assert (
        device_registry.async_get_device_by_identifier((DOMAIN, "SN1"), entry.entry_id)
        is None
    )
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "SN1_SOC") is None

    # Removed from runtime data.
    assert entry.runtime_data.bluetti_devices.devices == [other_device]
    assert "SN1" not in entry.runtime_data.coordinators
    coordinator.async_shutdown.assert_awaited_once()

    # A persistent notification was shown.
    mock_notify.assert_called_once()
    assert mock_notify.call_args.kwargs["notification_id"] == "bluetti_unbind_SN1"

    assert device._unbind_processed is True


async def test_handle_unbind_when_device_registry_entry_missing(
    hass: HomeAssistant,
) -> None:
    """Handle unbind when device registry entry missing."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test Device", sn="SN1", model="AC200L"
    )
    entry.runtime_data = BluettiRuntimeData(
        bluetti_devices=MagicMock(devices=[device]),
        stomp_client=MagicMock(),
        coordinators={},
    )
    device._hass = hass
    device._entry = entry
    device._entry_id = entry.entry_id

    # Must not raise even though there is no matching device registry entry.
    await device._handle_unbind()

    assert device._unbind_processed is True


async def test_async_refresh_from_api_triggers_unbind() -> None:
    """Async refresh from api triggers unbind."""
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L"
    )
    device._handle_unbind = AsyncMock()
    status_data = MagicMock(sn="SN1", isBindByCurUser="0")
    device._api_client = AsyncMock()
    device._api_client.get_device_status.return_value = MagicMock(data=[status_data])

    await device.async_refresh_from_api()

    device._handle_unbind.assert_awaited_once()


def _bound_device_with_registry_entries(
    hass: HomeAssistant, entry
) -> tuple[BluettiDevice, dr.DeviceEntry]:
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test Device", sn="SN1", model="AC200L"
    )
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "SN1")},
        name="Test Device",
        manufacturer="Bluetti",
        model="AC200L",
    )
    er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        "SN1_SOC",
        config_entry=entry,
        device_id=device_entry.id,
    )
    entry.runtime_data = BluettiRuntimeData(
        bluetti_devices=MagicMock(devices=[device]),
        stomp_client=MagicMock(),
        coordinators={"SN1": AsyncMock()},
    )
    device._hass = hass
    device._entry = entry
    device._entry_id = entry.entry_id
    return device, device_entry


async def test_handle_unbind_survives_entity_removal_error(hass: HomeAssistant) -> None:
    """Handle unbind survives entity removal error."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    device, _device_entry = _bound_device_with_registry_entries(hass, entry)

    with patch.object(
        er.EntityRegistry, "async_remove", side_effect=RuntimeError("boom")
    ):
        await device._handle_unbind()

    # Must complete without raising even though entity removal failed.
    assert device._unbind_processed is True


async def test_handle_unbind_survives_device_removal_error(hass: HomeAssistant) -> None:
    """Handle unbind survives device removal error."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    device, _device_entry = _bound_device_with_registry_entries(hass, entry)

    with patch.object(
        dr.DeviceRegistry, "async_remove_device", side_effect=RuntimeError("boom")
    ):
        await device._handle_unbind()

    assert device._unbind_processed is True


async def test_handle_unbind_survives_runtime_data_error(hass: HomeAssistant) -> None:
    """Handle unbind survives runtime data error."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    device, _device_entry = _bound_device_with_registry_entries(hass, entry)
    # Force an AttributeError when the cleanup code touches runtime_data.
    entry.runtime_data.bluetti_devices = None

    await device._handle_unbind()

    assert device._unbind_processed is True


async def test_handle_unbind_survives_notification_error(hass: HomeAssistant) -> None:
    """Handle unbind survives notification error."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    device, _device_entry = _bound_device_with_registry_entries(hass, entry)

    with patch(
        "homeassistant.components.bluetti_cloud.models.persistent_notification.async_create",
        side_effect=RuntimeError("boom"),
    ):
        await device._handle_unbind()

    assert device._unbind_processed is True


async def test_handle_unbind_survives_unexpected_outer_error(
    hass: HomeAssistant,
) -> None:
    """Handle unbind survives unexpected outer error.

    The outermost try/except exists so a single bad device (an unexpected
    error past every step's own except) never breaks setup.
    """
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    device, _device_entry = _bound_device_with_registry_entries(hass, entry)

    with patch.object(
        dr, "async_entries_for_config_entry", side_effect=RuntimeError("boom")
    ):
        # Must not raise: the outermost try/except catches anything
        # unexpected so a single bad device doesn't break setup.
        await device._handle_unbind()

    assert device._unbind_processed is True
