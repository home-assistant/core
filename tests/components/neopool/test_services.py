"""Tests for the NeoPool services."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from neopool_modbus.decoders import decode_device_time
import pytest
import voluptuous as vol

from homeassistant.components.neopool.const import DOMAIN
from homeassistant.components.neopool.helpers import prepare_device_time
from homeassistant.components.neopool.services import (
    SERVICE_GET_DEVICE_TIME,
    SERVICE_SET_DEVICE_TIME,
    SERVICE_SET_TIMER,
    SERVICE_WRITE_REGISTER,
    _get_coordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry


def _device_id(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    """Resolve the registry device_id for a loaded NeoPool config entry."""
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, entry.unique_id), entry.entry_id
    )
    assert device is not None
    return device.id


# ---------------------------------------------------------------------------
# set_timer
# ---------------------------------------------------------------------------


async def test_set_timer_writes_to_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A happy-path set_timer call forwards on/interval/period to the client."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TIMER,
        {
            "device_id": _device_id(hass, mock_config_entry),
            "timer": "filtration1",
            "start": "08:30",
            "stop": "10:15",
            "period": 1234,
        },
        blocking=True,
    )

    mock_neopool_client.write_timer.assert_awaited_once_with(
        "filtration1",
        {"on": 30600, "interval": 6300, "period": 1234},
    )


async def test_set_timer_forwards_enable_field(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """The enable field of set_timer is forwarded verbatim to the client."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TIMER,
        {
            "device_id": _device_id(hass, mock_config_entry),
            "timer": "relay_aux1",
            "enable": 3,
        },
        blocking=True,
    )

    mock_neopool_client.write_timer.assert_awaited_once_with(
        "relay_aux1",
        {"enable": 3},
    )


async def test_set_timer_falls_back_to_single_loaded_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Omitting device_id picks the only loaded entry."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TIMER,
        {
            "timer": "filtration1",
            "start": "08:30",
            "stop": "10:15",
        },
        blocking=True,
    )
    assert mock_neopool_client.write_timer.await_count == 1


@pytest.mark.usefixtures("mock_neopool_client")
async def test_set_timer_unknown_device_id_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A device_id that does not exist raises with translation key."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TIMER,
            {
                "device_id": "nonexistent",
                "timer": "filtration1",
                "start": "08:30",
                "stop": "10:15",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "device_not_found"


@pytest.mark.usefixtures("mock_neopool_client")
async def test_set_timer_explicit_device_id_must_be_loaded(
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
            SERVICE_SET_TIMER,
            {
                "device_id": device_id,
                "timer": "filtration1",
                "start": "08:30",
                "stop": "10:15",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "device_not_found"


async def test_set_timer_no_loaded_entry_raises(
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
            SERVICE_SET_TIMER,
            {"timer": "filtration1", "start": "08:30", "stop": "10:15"},
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
        SERVICE_SET_TIMER,
        {ATTR_DEVICE_ID: _device_id(hass, mock_config_entry)},
    )

    assert await _get_coordinator(hass, fake_call) is mock_config_entry.runtime_data


async def test_set_timer_invalid_timer_name_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """An unknown timer name raises before reaching the Modbus client."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TIMER,
            {"timer": "not_a_real_timer"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "invalid_timer"
    mock_neopool_client.write_timer.assert_not_awaited()


async def test_set_timer_invalid_time_format_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Malformed start/stop strings surface a translatable invalid_timer_time error.

    `hhmm_to_seconds()` raises ValueError on garbage input; without an
    explicit catch the user would see a raw traceback instead of the
    translated UI-friendly error.
    """
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TIMER,
            {"timer": "filtration1", "start": "not-a-time", "stop": "10:00"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "invalid_timer_time"
    mock_neopool_client.write_timer.assert_not_awaited()


async def test_set_timer_client_failure_translates_to_validation_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A Modbus write failure surfaces as a translated ServiceValidationError."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.write_timer = AsyncMock(side_effect=ConnectionError("nope"))

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TIMER,
            {
                "timer": "filtration1",
                "start": "08:30",
                "stop": "10:15",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "timer_failed"


# ---------------------------------------------------------------------------
# write_register
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("address", "value", "expected_addr", "expected_value"),
    [
        ("1539", "5", 1539, 5),
        ("0x0604", "0x0000", 0x0604, 0),
    ],
)
async def test_write_register_decimal_and_hex(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    address: str,
    value: str,
    expected_addr: int,
    expected_value: int,
) -> None:
    """Decimal and 0x-prefixed strings are both accepted."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_write_register = AsyncMock(
        return_value={"value": expected_value, "confirmed": expected_value}
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_WRITE_REGISTER,
        {
            "device_id": _device_id(hass, mock_config_entry),
            "address": address,
            "value": value,
        },
        blocking=True,
    )
    mock_neopool_client.async_write_register.assert_awaited_once_with(
        expected_addr, expected_value, apply=True
    )


async def test_write_register_apply_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Setting apply=false skips the EEPROM commit on the client side."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_write_register = AsyncMock(
        return_value={"value": 7, "confirmed": 7}
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_WRITE_REGISTER,
        {
            "device_id": _device_id(hass, mock_config_entry),
            "address": "1539",
            "value": "7",
            "apply": False,
        },
        blocking=True,
    )
    mock_neopool_client.async_write_register.assert_awaited_once_with(
        1539, 7, apply=False
    )


async def test_write_register_invalid_hex_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """An unparsable hex address raises before any write."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_WRITE_REGISTER,
            {
                "device_id": _device_id(hass, mock_config_entry),
                "address": "0xZZZZ",
                "value": "5",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "invalid_register_type"
    mock_neopool_client.async_write_register.assert_not_awaited()


@pytest.mark.usefixtures("mock_neopool_client")
async def test_write_register_out_of_range_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Values above 65535 are rejected by parse_register_int."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_WRITE_REGISTER,
            {
                "device_id": _device_id(hass, mock_config_entry),
                "address": "1539",
                "value": "70000",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "register_out_of_range"


async def test_write_register_verification_mismatch_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A read-back that disagrees with the write surfaces a clear error."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_write_register = AsyncMock(
        return_value={"value": 5, "confirmed": 99}
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_WRITE_REGISTER,
            {
                "device_id": _device_id(hass, mock_config_entry),
                "address": "1539",
                "value": "5",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "write_verification_failed"


async def test_write_register_returns_none_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """When the client returns None we surface 'write_failed'."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_write_register = AsyncMock(return_value=None)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_WRITE_REGISTER,
            {
                "device_id": _device_id(hass, mock_config_entry),
                "address": "1539",
                "value": "5",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "write_failed"


async def test_write_register_client_failure_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Modbus exceptions are wrapped in a translated ServiceValidationError."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_write_register = AsyncMock(
        side_effect=ConnectionError("Modbus down")
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_WRITE_REGISTER,
            {
                "device_id": _device_id(hass, mock_config_entry),
                "address": "1539",
                "value": "5",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "register_write_failed"


# ---------------------------------------------------------------------------
# read_register
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("address", "expected_addr"),
    [
        ("258", 0x0102),  # decimal MEASURE_PH
        ("0x0102", 0x0102),
        ("0x0500", 0x0500),  # USER MBF_PAR_ION
    ],
)
async def test_read_register_returns_single_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    address: str,
    expected_addr: int,
) -> None:
    """count=1 (default) returns both `values` list and `value` scalar in the response."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_register = AsyncMock(return_value=[720])

    response = await hass.services.async_call(
        DOMAIN,
        "read_register",
        {"device_id": _device_id(hass, mock_config_entry), "address": address},
        blocking=True,
        return_response=True,
    )

    mock_neopool_client.async_read_register.assert_awaited_once_with(expected_addr, 1)
    assert response == {
        "address": f"0x{expected_addr:04X}",
        "count": 1,
        "values": [720],
        "value": 720,
    }


async def test_read_register_count_returns_full_list(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """count>1 returns `values` but no scalar `value`."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_register = AsyncMock(
        return_value=[100, 200, 300, 400]
    )

    response = await hass.services.async_call(
        DOMAIN,
        "read_register",
        {
            "device_id": _device_id(hass, mock_config_entry),
            "address": "0x0500",
            "count": 4,
        },
        blocking=True,
        return_response=True,
    )

    mock_neopool_client.async_read_register.assert_awaited_once_with(0x0500, 4)
    assert response == {
        "address": "0x0500",
        "count": 4,
        "values": [100, 200, 300, 400],
    }
    assert "value" not in response


@pytest.mark.parametrize("count", [0, -1, 32, 100])
async def test_read_register_count_out_of_range_rejected_by_schema(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    count: int,
) -> None:
    """Schema vol.Range(min=1, max=31) rejects bad counts before we touch the client."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_register = AsyncMock()

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "read_register",
            {
                "device_id": _device_id(hass, mock_config_entry),
                "address": "0x0500",
                "count": count,
            },
            blocking=True,
            return_response=True,
        )
    mock_neopool_client.async_read_register.assert_not_awaited()


async def test_read_register_library_error_translates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """NeoPoolError from the library surfaces as ServiceValidationError."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_register = AsyncMock(
        side_effect=ConnectionError("Modbus down")
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "read_register",
            {"device_id": _device_id(hass, mock_config_entry), "address": "0x0102"},
            blocking=True,
            return_response=True,
        )
    assert exc_info.value.translation_key == "register_read_failed"


async def test_read_register_value_error_translates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """ValueError raised by the library (e.g. boundary cross) is also handled."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_register = AsyncMock(
        side_effect=ValueError("boundary")
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "read_register",
            {
                "device_id": _device_id(hass, mock_config_entry),
                "address": "0x01F0",
                "count": 20,
            },
            blocking=True,
            return_response=True,
        )
    assert exc_info.value.translation_key == "register_read_failed"


# ---------------------------------------------------------------------------
# get_device_time
# ---------------------------------------------------------------------------


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
    """A library error while reading the time surfaces as ServiceValidationError."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_register = AsyncMock(
        side_effect=ConnectionError("Modbus down")
    )

    with pytest.raises(ServiceValidationError) as exc_info:
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
    """A truncated clock read surfaces as ServiceValidationError, not IndexError."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_register = AsyncMock(return_value=[123])

    with pytest.raises(ServiceValidationError) as exc_info:
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
    """An unparseable clock value surfaces as ServiceValidationError, not a crash."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_register = AsyncMock(return_value=[0, 0])

    with (
        patch(
            "homeassistant.components.neopool.services.decode_device_time",
            return_value=None,
        ),
        pytest.raises(ServiceValidationError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_DEVICE_TIME,
            {"device_id": _device_id(hass, mock_config_entry)},
            blocking=True,
            return_response=True,
        )
    assert exc_info.value.translation_key == "device_time_read_failed"


# ---------------------------------------------------------------------------
# set_device_time
# ---------------------------------------------------------------------------


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

    with pytest.raises(ServiceValidationError) as exc_info:
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
    """A library error while syncing surfaces as ServiceValidationError."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_sync_device_time = AsyncMock(
        side_effect=ConnectionError("Modbus down")
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DEVICE_TIME,
            {"device_id": _device_id(hass, mock_config_entry)},
            blocking=True,
        )
    assert exc_info.value.translation_key == "device_time_write_failed"
