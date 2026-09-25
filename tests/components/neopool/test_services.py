"""Tests for the NeoPool services."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from neopool_modbus.decoders import decode_device_time
import pytest

from homeassistant.components.neopool.const import DOMAIN
from homeassistant.components.neopool.helpers import prepare_device_time
from homeassistant.components.neopool.services import (
    SERVICE_GET_DEVICE_TIME,
    SERVICE_SET_DEVICE_TIME,
    _get_coordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, MockUser


def _device_id(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    """Resolve the registry device_id for a loaded NeoPool config entry."""
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, entry.unique_id), entry.entry_id
    )
    assert device is not None
    return device.id


async def test_falls_back_to_single_loaded_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Omitting device_id picks the only loaded entry."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DEVICE_TIME,
        {},
        blocking=True,
    )
    assert mock_neopool_client.async_sync_device_time.await_count == 1


@pytest.mark.usefixtures("mock_neopool_client")
async def test_unknown_device_id_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A device_id that does not exist raises with translation key."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DEVICE_TIME,
            {"device_id": "nonexistent"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "device_not_found"


@pytest.mark.usefixtures("mock_neopool_client")
async def test_empty_device_id_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An explicitly empty device_id is a bad target, not an omitted one.

    cv.string accepts "", so the resolver must route it through target
    resolution and raise device_not_found rather than silently falling back
    to the only loaded entry.
    """
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DEVICE_TIME,
            {"device_id": ""},
            blocking=True,
        )
    assert exc_info.value.translation_key == "device_not_found"


@pytest.mark.usefixtures("mock_neopool_client")
async def test_explicit_device_id_must_be_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Explicit device_id whose entry is NOT_LOADED is rejected.

    Routing a service call to a stale or unloaded entry would surface
    confusing AttributeError downstream, the resolver requires the
    matching entry to be LOADED.
    """
    await setup_integration(hass, mock_config_entry)
    device_id = _device_id(hass, mock_config_entry)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DEVICE_TIME,
            {"device_id": device_id},
            blocking=True,
        )
    assert exc_info.value.translation_key == "device_not_found"


async def test_no_loaded_entry_raises(
    hass: HomeAssistant,
) -> None:
    """Calling the service before any entry is loaded raises."""
    # async_setup is invoked by HA before any entry, so the service is
    # registered globally, but no LOADED entry exists yet.

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DEVICE_TIME,
            {},
            blocking=True,
        )
    assert exc_info.value.translation_key == "no_loaded_entry"


async def test_get_coordinator_raises_when_runtime_data_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """If a LOADED entry has no runtime_data, _get_coordinator raises.

    Direct unit test on the helper, drives the defensive 'coordinator is None'
    branch without relying on the entry-state ordering inside HA's
    config_entries machinery.
    """

    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    object.__setattr__(mock_config_entry, "runtime_data", None)

    fake_call = MagicMock()
    fake_call.data = {}

    with pytest.raises(ServiceValidationError) as exc_info:
        await _get_coordinator(hass, fake_call)
    assert exc_info.value.translation_key == "no_coordinator"


async def test_get_coordinator_raises_when_multiple_entries_and_no_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Omitting device_id with more than one loaded entry is ambiguous.

    Direct unit test on the helper: two LOADED entries and no device_id in
    the call data must raise 'multiple_entries_no_device' rather than
    silently picking one.
    """
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    object.__setattr__(mock_config_entry, "runtime_data", MagicMock())

    second = MockConfigEntry(domain=DOMAIN, unique_id="0987654321")
    second.add_to_hass(hass)
    second.mock_state(hass, ConfigEntryState.LOADED)
    object.__setattr__(second, "runtime_data", MagicMock())

    fake_call = MagicMock()
    fake_call.data = {}

    with pytest.raises(ServiceValidationError) as exc_info:
        await _get_coordinator(hass, fake_call)
    assert exc_info.value.translation_key == "multiple_entries_no_device"


async def test_get_coordinator_resolves_by_device_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """An explicit device_id resolves to that entry's coordinator."""
    await setup_integration(hass, mock_config_entry)

    fake_call = ServiceCall(
        hass,
        DOMAIN,
        SERVICE_SET_DEVICE_TIME,
        {ATTR_DEVICE_ID: _device_id(hass, mock_config_entry)},
    )

    assert await _get_coordinator(hass, fake_call) is mock_config_entry.runtime_data


async def test_get_device_time_reads_fresh_from_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """The service reads only the clock registers fresh, ignoring the cache."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    # A stale cached value that must NOT be used.
    coordinator.data["MBF_PAR_TIME"] = prepare_device_time(hass) - 3600
    # A device clock two minutes ahead of Home Assistant time, split into words.
    device_ts = prepare_device_time(hass) + 120
    mock_neopool_client.async_read_register = AsyncMock(
        return_value=[device_ts & 0xFFFF, device_ts >> 16]
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_DEVICE_TIME,
        {"device_id": _device_id(hass, mock_config_entry)},
        blocking=True,
        return_response=True,
    )

    mock_neopool_client.async_read_register.assert_awaited_once_with(0x0408, 2)
    tz = dt_util.get_time_zone(hass.config.time_zone) or UTC
    assert response is not None
    assert response["device_time"] == decode_device_time(device_ts, tz).isoformat()
    assert response["drift_seconds"] == pytest.approx(120, abs=2)
    # ha_time is rounded to whole seconds to match the device RTC precision.
    assert datetime.fromisoformat(response["ha_time"]).microsecond == 0


async def test_get_device_time_read_error_translates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A library error while reading the time surfaces as HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_register = AsyncMock(
        side_effect=ConnectionError("Modbus down")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_DEVICE_TIME,
            {"device_id": _device_id(hass, mock_config_entry)},
            blocking=True,
            return_response=True,
        )
    assert exc_info.value.translation_key == "device_time_read_failed"


async def test_get_device_time_short_read_translates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A truncated clock read surfaces as HomeAssistantError, not IndexError."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_register = AsyncMock(return_value=[123])

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_DEVICE_TIME,
            {"device_id": _device_id(hass, mock_config_entry)},
            blocking=True,
            return_response=True,
        )
    assert exc_info.value.translation_key == "device_time_read_failed"


async def test_get_device_time_undecodable_translates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """An unparsable clock value surfaces as HomeAssistantError, not a crash."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_register = AsyncMock(return_value=[0, 0])

    with (
        patch(
            "homeassistant.components.neopool.services.decode_device_time",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_DEVICE_TIME,
            {"device_id": _device_id(hass, mock_config_entry)},
            blocking=True,
            return_response=True,
        )
    assert exc_info.value.translation_key == "device_time_read_failed"


async def test_set_device_time_writes_ha_now(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """set_device_time encodes Home Assistant time and syncs the device RTC."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_sync_device_time = AsyncMock(return_value={"value": 1})

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DEVICE_TIME,
        {"device_id": _device_id(hass, mock_config_entry)},
        blocking=True,
    )

    mock_neopool_client.async_sync_device_time.assert_awaited_once()
    written = mock_neopool_client.async_sync_device_time.await_args.args[0]
    assert written == pytest.approx(prepare_device_time(hass), abs=2)


async def test_set_device_time_none_response_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A None sync result (unconfirmed write) raises a translated error."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_sync_device_time = AsyncMock(return_value=None)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DEVICE_TIME,
            {"device_id": _device_id(hass, mock_config_entry)},
            blocking=True,
        )
    assert exc_info.value.translation_key == "device_time_write_failed"


async def test_set_device_time_error_translates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A library error while syncing surfaces as HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_sync_device_time = AsyncMock(
        side_effect=ConnectionError("Modbus down")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DEVICE_TIME,
            {"device_id": _device_id(hass, mock_config_entry)},
            blocking=True,
        )
    assert exc_info.value.translation_key == "device_time_write_failed"


async def test_set_device_time_denied_for_non_admin(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    hass_read_only_user: MockUser,
) -> None:
    """A state-changing service is admin-only and rejects non-admin callers."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DEVICE_TIME,
            {"device_id": _device_id(hass, mock_config_entry)},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    mock_neopool_client.async_sync_device_time.assert_not_awaited()


async def test_get_device_time_rejected_in_winter_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Winter mode means no Modbus traffic, so reading the time is rejected."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_register = AsyncMock()
    hass.config_entries.async_update_entry(mock_config_entry, pref_disable_polling=True)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_DEVICE_TIME,
            {"device_id": _device_id(hass, mock_config_entry)},
            blocking=True,
            return_response=True,
        )
    assert exc_info.value.translation_key == "winter_mode_active"
    mock_neopool_client.async_read_register.assert_not_awaited()


async def test_set_device_time_rejected_in_winter_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Winter mode means no Modbus traffic, so writing the time is rejected."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_sync_device_time = AsyncMock()
    hass.config_entries.async_update_entry(mock_config_entry, pref_disable_polling=True)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DEVICE_TIME,
            {"device_id": _device_id(hass, mock_config_entry)},
            blocking=True,
        )
    assert exc_info.value.translation_key == "winter_mode_active"
    mock_neopool_client.async_sync_device_time.assert_not_awaited()
