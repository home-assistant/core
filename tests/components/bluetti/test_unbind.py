"""Tests for BluettiDevice._handle_unbind and remaining BluettiData behavior."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.bluetti import BluettiRuntimeData
from homeassistant.components.bluetti.const import DOMAIN
from homeassistant.components.bluetti.models import BluettiData, BluettiDevice
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_bluetti_data_test_connection_returns_true() -> None:
    """Bluetti data test connection returns true."""
    data = BluettiData.__new__(BluettiData)
    assert await data.test_connection() is True


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
        "homeassistant.components.bluetti.models.asyncio.run_coroutine_threadsafe"
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
        "homeassistant.components.bluetti.models.asyncio.run_coroutine_threadsafe"
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
    """Handle unbind full cleanup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            "devices": ["SN1", "SN2"],
            "modbus": {"SN1": {"host": "10.2.1.60", "port": 502}},
        },
    )
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
    modbus_coordinator = AsyncMock()
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[device, other_device]),
        stomp_client=MagicMock(),
        coordinators={"SN1": coordinator, "SN2": MagicMock()},
        modbus_coordinators={"SN1": modbus_coordinator},
    )

    device._hass = hass
    device._entry = entry
    device._entry_id = entry.entry_id

    with (
        patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload,
        patch(
            "homeassistant.components.bluetti.models.persistent_notification.async_create"
        ) as mock_notify,
    ):
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
    assert "SN1" not in entry.runtime_data.modbus_coordinators
    coordinator.async_shutdown.assert_awaited_once()
    modbus_coordinator.async_shutdown.assert_awaited_once()

    # Removed from the config entry's enabled devices.
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.options["devices"] == ["SN2"]
    assert updated.options["modbus"] == {}

    # A persistent notification was shown.
    mock_notify.assert_called_once()
    assert mock_notify.call_args.kwargs["notification_id"] == "bluetti_unbind_SN1"

    mock_reload.assert_awaited_once_with(entry.entry_id)


async def test_handle_unbind_when_device_registry_entry_missing(
    hass: HomeAssistant,
) -> None:
    """Handle unbind when device registry entry missing."""
    entry = MockConfigEntry(domain=DOMAIN, options={"devices": ["SN1"]})
    entry.add_to_hass(hass)

    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test Device", sn="SN1", model="AC200L"
    )
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[device]),
        stomp_client=MagicMock(),
        coordinators={},
    )
    device._hass = hass
    device._entry = entry
    device._entry_id = entry.entry_id

    with patch.object(hass.config_entries, "async_reload", AsyncMock()):
        await device._handle_unbind()
        await hass.async_block_till_done()

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.options["devices"] == []


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
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[device]),
        stomp_client=MagicMock(),
        coordinators={"SN1": MagicMock()},
    )
    device._hass = hass
    device._entry = entry
    device._entry_id = entry.entry_id
    return device, device_entry


async def test_handle_unbind_survives_entity_removal_error(hass: HomeAssistant) -> None:
    """Handle unbind survives entity removal error."""
    entry = MockConfigEntry(domain=DOMAIN, options={"devices": ["SN1"]})
    entry.add_to_hass(hass)
    device, _device_entry = _bound_device_with_registry_entries(hass, entry)

    with (
        patch.object(hass.config_entries, "async_reload", AsyncMock()),
        patch.object(
            er.EntityRegistry, "async_remove", side_effect=RuntimeError("boom")
        ),
    ):
        await device._handle_unbind()
        await hass.async_block_till_done()

    # Must complete without raising even though entity removal failed.
    assert device._unbind_processed is True


async def test_handle_unbind_survives_device_removal_error(hass: HomeAssistant) -> None:
    """Handle unbind survives device removal error."""
    entry = MockConfigEntry(domain=DOMAIN, options={"devices": ["SN1"]})
    entry.add_to_hass(hass)
    device, _device_entry = _bound_device_with_registry_entries(hass, entry)

    with (
        patch.object(hass.config_entries, "async_reload", AsyncMock()),
        patch.object(
            dr.DeviceRegistry, "async_remove_device", side_effect=RuntimeError("boom")
        ),
    ):
        await device._handle_unbind()
        await hass.async_block_till_done()

    assert device._unbind_processed is True


async def test_handle_unbind_survives_runtime_data_error(hass: HomeAssistant) -> None:
    """Handle unbind survives runtime data error."""
    entry = MockConfigEntry(domain=DOMAIN, options={"devices": ["SN1"]})
    entry.add_to_hass(hass)
    device, _device_entry = _bound_device_with_registry_entries(hass, entry)
    # Force an AttributeError when the cleanup code touches runtime_data.
    entry.runtime_data.bluetti_devices = None

    with patch.object(hass.config_entries, "async_reload", AsyncMock()):
        await device._handle_unbind()
        await hass.async_block_till_done()

    assert device._unbind_processed is True


async def test_handle_unbind_survives_config_entry_update_error(
    hass: HomeAssistant,
) -> None:
    """Handle unbind survives config entry update error."""
    entry = MockConfigEntry(domain=DOMAIN, options={"devices": ["SN1"]})
    entry.add_to_hass(hass)
    device, _device_entry = _bound_device_with_registry_entries(hass, entry)

    with (
        patch.object(hass.config_entries, "async_reload", AsyncMock()),
        patch.object(
            hass.config_entries, "async_update_entry", side_effect=RuntimeError("boom")
        ),
    ):
        await device._handle_unbind()
        await hass.async_block_till_done()

    assert device._unbind_processed is True


async def test_handle_unbind_survives_notification_error(hass: HomeAssistant) -> None:
    """Handle unbind survives notification error."""
    entry = MockConfigEntry(domain=DOMAIN, options={"devices": ["SN1"]})
    entry.add_to_hass(hass)
    device, _device_entry = _bound_device_with_registry_entries(hass, entry)

    with (
        patch.object(hass.config_entries, "async_reload", AsyncMock()),
        patch(
            "homeassistant.components.bluetti.models.persistent_notification.async_create",
            side_effect=RuntimeError("boom"),
        ),
    ):
        await device._handle_unbind()
        await hass.async_block_till_done()

    assert device._unbind_processed is True


async def test_handle_unbind_survives_reload_error(hass: HomeAssistant) -> None:
    """Handle unbind survives reload error."""
    entry = MockConfigEntry(domain=DOMAIN, options={"devices": ["SN1"]})
    entry.add_to_hass(hass)
    device, _device_entry = _bound_device_with_registry_entries(hass, entry)

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(side_effect=RuntimeError("boom"))
    ):
        await device._handle_unbind()
        # The reload runs in a background task; let it fail and log.
        await hass.async_block_till_done()

    assert device._unbind_processed is True


async def test_handle_unbind_when_device_not_in_options(hass: HomeAssistant) -> None:
    """Handle unbind when device not in options."""
    entry = MockConfigEntry(domain=DOMAIN, options={"devices": ["SN2"]})
    entry.add_to_hass(hass)
    device, _device_entry = _bound_device_with_registry_entries(hass, entry)

    with patch.object(hass.config_entries, "async_reload", AsyncMock()):
        await device._handle_unbind()
        await hass.async_block_till_done()

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.options["devices"] == ["SN2"]


async def test_handle_unbind_survives_unexpected_outer_error(
    hass: HomeAssistant,
) -> None:
    """Handle unbind survives unexpected outer error."""
    entry = MockConfigEntry(domain=DOMAIN, options={"devices": ["SN1"]})
    entry.add_to_hass(hass)
    device, _device_entry = _bound_device_with_registry_entries(hass, entry)

    with patch.object(
        dr, "async_entries_for_config_entry", side_effect=RuntimeError("boom")
    ):
        # Must not raise: the outermost try/except catches anything
        # unexpected so a single bad device doesn't break setup.
        await device._handle_unbind()

    assert device._unbind_processed is True
