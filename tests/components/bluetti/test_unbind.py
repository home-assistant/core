"""Tests for BluettiDevice._handle_unbind and remaining BluettiData behavior."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from pybluetti import UnifyResponse, UserProduct
import pytest

from homeassistant.components.bluetti import BluettiRuntimeData, _async_update_listener
from homeassistant.components.bluetti.config_flow import BluettiConfigFlow
from homeassistant.components.bluetti.const import (
    ACCOUNT_UNIQUE_ID,
    DOMAIN,
    INTEGRATION_NAME,
)
from homeassistant.components.bluetti.models import BluettiData, BluettiDevice
from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
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
    """Handle unbind full cleanup.

    mock_reload's assert_awaited_once_with below is also a regression check
    for a fixed duplicate-reload bug: the options update a few lines below
    (options={..., "devices": new_devices}) fires this listener once.
    _handle_unbind() used to ALSO schedule its own explicit reload after a
    fixed 1-second delay on top of that - two reloads (serialized by
    entry.setup_lock, not concurrent, but still one full unload+setup too
    many) for a single unbind, and unconditionally even when the device
    wasn't in the options list to begin with, so it could also fire after
    the entry itself was gone.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={"devices": ["SN1", "SN2"]},
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
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[device, other_device]),
        stomp_client=MagicMock(),
        coordinators={"SN1": coordinator, "SN2": MagicMock()},
    )

    device._hass = hass
    device._entry = entry
    device._entry_id = entry.entry_id

    # Mirrors what async_setup_entry() registers on a real, fully-loaded
    # entry - _handle_unbind() itself no longer reloads explicitly (see the
    # regression test below), it relies entirely on this listener firing
    # from its own options update.
    entry.add_update_listener(_async_update_listener)

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
    coordinator.async_shutdown.assert_awaited_once()

    # Removed from the config entry's enabled devices.
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.options["devices"] == ["SN2"]

    # A persistent notification was shown.
    mock_notify.assert_called_once()
    assert mock_notify.call_args.kwargs["notification_id"] == "bluetti_unbind_SN1"

    mock_reload.assert_awaited_once_with(entry.entry_id)


async def test_unbind_then_rebind_uses_fresh_metadata_not_stale_cache(
    hass: HomeAssistant,
) -> None:
    """A device re-bound after being unbound must use fresh cloud data.

    Regression test: _handle_unbind() used to only remove the device from
    entry.options["devices"], never from entry.data["products"] - a later
    re-bind of the same serial was
    treated as "already cached" by config_flow.py's product merge (it
    only adds products whose sn isn't already present in
    entry.data["products"]), silently keeping the stale name/model/state
    from before the unbind instead of the fresh data the re-bind just
    fetched from the cloud.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "auth_implementation": "bluetti",
            "token": {"access_token": "tok"},
            "products": [
                {"sn": "SN1", "name": "Old Name", "stateList": [], "online": "1"}
            ],
        },
        options={"devices": ["SN1"]},
    )
    entry.add_to_hass(hass)

    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Old Name", sn="SN1", model="AC200L"
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

    with patch(
        "homeassistant.components.bluetti.models.persistent_notification.async_create"
    ):
        await device._handle_unbind()
        await hass.async_block_till_done()

    unbound = hass.config_entries.async_get_entry(entry.entry_id)
    assert unbound.options["devices"] == []
    assert unbound.data["products"] == []

    # Re-bind the same serial: the cloud now reports a different name.
    # A plain fresh flow finding an existing entry aborts as
    # already_configured instead of merging (see config_flow.py) - use the
    # reconfigure/reauth re-run path, the only one allowed to merge.
    flow = BluettiConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": SOURCE_RECONFIGURE}
    flow._oauth_data = {
        "auth_implementation": "bluetti",
        "token": {"access_token": "tok2", "expires_at": 9999999999},
    }
    flow._products = [UserProduct(sn="SN1", name="New Name", stateList=[], online="1")]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)

    with pytest.raises(AbortFlow) as exc_info:
        await flow.async_step_select_devices(user_input={"devices": ["SN1"]})
    assert exc_info.value.reason == "success"

    rebound = hass.config_entries.async_get_entry(entry.entry_id)
    assert [p["name"] for p in rebound.data["products"]] == ["New Name"]


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
