"""Tests for the NeoPool select platform."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from neopool_modbus import NeoPoolError
from neopool_modbus.registers import ConfigKind, FiltValveMode, RelayKind, RelayMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_OPTION, SERVICE_SELECT_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import MOCK_POOL_DATA

from tests.common import MockConfigEntry, snapshot_platform


def _select_entity_id(
    hass: HomeAssistant, entry: MockConfigEntry, key_lower_suffix: str
) -> str:
    """Resolve a select entity by its trailing unique_id segment."""
    registry = er.async_get(hass)
    entries = [
        e
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.domain == SELECT_DOMAIN and e.unique_id.endswith(f"_{key_lower_suffix}")
    ]
    assert entries, (
        f"no select entity ending in _{key_lower_suffix}, found: "
        + ", ".join(
            e.unique_id
            for e in er.async_entries_for_config_entry(registry, entry.entry_id)
            if e.domain == SELECT_DOMAIN
        )
    )
    return entries[0].entity_id


async def _select_option(hass: HomeAssistant, entity_id: str, option: str) -> None:
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {"entity_id": entity_id, ATTR_OPTION: option},
        blocking=True,
    )


async def test_filt_mode_select_writes_register(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Selecting a filtration mode delegates to the lib's async_set_filtration_mode."""
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(hass, mock_config_entry_timers, "mbf_par_filt_mode")

    mock_neopool_client.async_set_filtration_mode.reset_mock()
    await _select_option(hass, entity_id, "auto")
    mock_neopool_client.async_set_filtration_mode.assert_awaited_once_with("auto")


async def test_filt_mode_leaving_manual_delegates_exit_to_lib(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Leaving manual mode is a single lib call; the lib sequences the pump stop.

    The manual-mode exit (pump off + settle delay) lives in
    async_set_filtration_mode, so the platform must not stop the pump itself.
    """

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILT_MODE": 0,
        "filtration_mode": "manual",
        "MBF_PAR_FILT_MANUAL_STATE": 1,
    }
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _select_entity_id(hass, mock_config_entry_timers, "mbf_par_filt_mode")
    mock_neopool_client.async_set_manual_filtration.reset_mock()
    mock_neopool_client.async_set_filtration_mode.reset_mock()
    await _select_option(hass, entity_id, "auto")

    mock_neopool_client.async_set_manual_filtration.assert_not_awaited()
    mock_neopool_client.async_set_filtration_mode.assert_awaited_once_with("auto")


async def test_filt_mode_backwash_option_is_display_only(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Backwash (13) is offered only when the device already reports that mode.

    Writing 13 does not start a cleaning cycle (that is the backwash switch),
    so the option is hidden otherwise, even when a filter valve is present.
    """
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(hass, mock_config_entry_timers, "mbf_par_filt_mode")
    state = hass.states.get(entity_id)
    assert state is not None
    assert "backwash" not in state.attributes["options"]

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILT_MODE": 13,
    }
    await mock_config_entry_timers.runtime_data.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert "backwash" in state.attributes["options"]

    # Reselecting the display-only backwash option must not write to the device.
    mock_neopool_client.async_set_filtration_mode.reset_mock()
    await _select_option(hass, entity_id, "backwash")
    mock_neopool_client.async_set_filtration_mode.assert_not_awaited()


async def test_filtvalve_period_minutes_writes_mapped_register(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Mapped-register selects reverse-lookup the option label and dispatch it."""
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(
        hass, mock_config_entry_timers, "mbf_par_filtvalve_period_minutes"
    )
    mock_neopool_client.async_set_config_option.reset_mock()
    await _select_option(hass, entity_id, "1_week")
    mock_neopool_client.async_set_config_option.assert_any_await(
        ConfigKind.FILTVALVE_PERIOD_MINUTES, 10080
    )


async def test_filtvalve_interval_writes_mapped_register(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """The Backwash Duration select maps its label to the interval register."""
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(
        hass, mock_config_entry_timers, "mbf_par_filtvalve_interval"
    )
    mock_neopool_client.async_set_config_option.reset_mock()
    await _select_option(hass, entity_id, "150s")
    mock_neopool_client.async_set_config_option.assert_any_await(
        ConfigKind.FILTVALVE_INTERVAL, 150
    )


async def test_relay_activation_delay_uses_dedicated_lib_method(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """The activation-delay select calls the lib method with user-facing seconds.

    The library owns the firmware -10 s offset, so the integration passes the
    selected seconds unchanged.
    """
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(
        hass, mock_config_entry_timers, "mbf_par_relay_activation_delay"
    )
    mock_neopool_client.async_set_relay_activation_delay.reset_mock()
    await _select_option(hass, entity_id, "20")
    mock_neopool_client.async_set_relay_activation_delay.assert_any_await(20)
    # The generic raw-write path is not used for this entity.
    mock_neopool_client.async_set_config_option.assert_not_awaited()


async def test_filtvalve_interval_current_option_reads_register(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Backwash Duration reflects the register value, with a suffix fallback off-map."""
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(
        hass, mock_config_entry_timers, "mbf_par_filtvalve_interval"
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "150s"

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILTVALVE_INTERVAL": 200,
    }
    await mock_config_entry_timers.runtime_data.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "200s"


async def test_filtvalve_mode_select_switches_via_lib_api(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """The Backwash Valve Mode select delegates to async_set_filtvalve_mode.

    Mirrors the relay-mode select: 'auto' maps to FiltValveMode.AUTO and the
    returned override merges in optimistically so current_option flips.
    """
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(
        hass, mock_config_entry_timers, "mbf_par_filtvalve_mode"
    )
    mock_neopool_client.async_set_filtvalve_mode = AsyncMock(
        return_value={"MBF_PAR_FILTVALVE_MODE": FiltValveMode.AUTO.value},
    )
    await _select_option(hass, entity_id, "auto")
    mock_neopool_client.async_set_filtvalve_mode.assert_awaited_once_with(
        FiltValveMode.AUTO
    )
    assert hass.states.get(entity_id).state == "auto"


async def test_filtvalve_mode_manual_writes_always_off(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Selecting 'manual' from AUTO pins the valve OFF (FiltValveMode.ALWAYS_OFF)."""
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILTVALVE_MODE": FiltValveMode.AUTO.value,
    }
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(
        hass, mock_config_entry_timers, "mbf_par_filtvalve_mode"
    )
    mock_neopool_client.async_set_filtvalve_mode = AsyncMock(
        return_value={"MBF_PAR_FILTVALVE_MODE": FiltValveMode.ALWAYS_OFF.value},
    )
    await _select_option(hass, entity_id, "manual")
    mock_neopool_client.async_set_filtvalve_mode.assert_awaited_once_with(
        FiltValveMode.ALWAYS_OFF
    )


async def test_filtvalve_mode_manual_to_manual_is_noop(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Selecting 'manual' when the valve already is manual does not write."""
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILTVALVE_MODE": FiltValveMode.ALWAYS_OFF.value,
    }
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(
        hass, mock_config_entry_timers, "mbf_par_filtvalve_mode"
    )
    mock_neopool_client.async_set_filtvalve_mode = AsyncMock(return_value={})
    await _select_option(hass, entity_id, "manual")
    mock_neopool_client.async_set_filtvalve_mode.assert_not_awaited()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (FiltValveMode.AUTO.value, "auto"),
        (FiltValveMode.ALWAYS_ON.value, "manual"),
        (FiltValveMode.ALWAYS_OFF.value, "manual"),
    ],
)
async def test_filtvalve_mode_current_option_maps_register(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    raw: int,
    expected: str,
) -> None:
    """current_option reduces the 3 register values to auto / manual.

    AUTO (1) -> 'auto'; ALWAYS_ON (3) and ALWAYS_OFF (4) -> 'manual'.
    """
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(
        hass, mock_config_entry_timers, "mbf_par_filtvalve_mode"
    )

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILTVALVE_MODE": raw,
    }
    await mock_config_entry_timers.runtime_data.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected


async def test_filtvalve_mode_maps_communication_error_to_home_assistant_error(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A NeoPoolError from async_set_filtvalve_mode surfaces as HomeAssistantError."""
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(
        hass, mock_config_entry_timers, "mbf_par_filtvalve_mode"
    )
    mock_neopool_client.async_set_filtvalve_mode = AsyncMock(
        side_effect=NeoPoolError("boom"),
    )
    with pytest.raises(HomeAssistantError):
        await _select_option(hass, entity_id, "auto")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cell_boost_active_redox_writes_composite_value(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """active_redox option writes 0x05A0 to the cell boost register."""
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _select_entity_id(hass, mock_config_entry_timers, "mbf_cell_boost")
    mock_neopool_client.async_set_cell_boost.reset_mock()
    await _select_option(hass, entity_id, "active_redox")
    mock_neopool_client.async_set_cell_boost.assert_awaited_once_with("active_redox")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, "inactive"),
        (0x8000, "active"),
        (0x0500 | 0x00A0, "active_redox"),
        (0x1234, "inactive"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cell_boost_current_option_decodes_register_bits(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    raw: int,
    expected: str,
) -> None:
    """current_option for MBF_CELL_BOOST decodes the register bit pattern."""
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_CELL_BOOST": raw,
    }
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _select_entity_id(hass, mock_config_entry_timers, "mbf_cell_boost")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected


async def test_relay_mode_current_option_handles_disabled_state(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Verify the disabled-state branch of a relay_mode select.

    The options list adds 'disabled' when enable=0, and current_option
    returns 'disabled' for that state.
    """
    mock_neopool_client.read_all_timers.side_effect = None
    mock_neopool_client.read_all_timers.return_value = {
        "relay_aux1": {
            "enable": 0,
            "on": 0,
            "interval": 0,
            "period": 0,
            "countdown": 0,
            "stop": None,
        }
    }
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _select_entity_id(hass, mock_config_entry_timers, "relay_aux1_mode")
    state = hass.states.get(entity_id)
    assert state is not None
    assert "disabled" in state.attributes["options"]
    assert state.state == "disabled"


async def test_timer_period_options_and_current_option(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """timer_period select reads options + current_option from coordinator data."""
    mock_neopool_client.read_all_timers.side_effect = None
    mock_neopool_client.read_all_timers.return_value = {
        "relay_aux1": {
            "enable": 4,
            "on": 0,
            "interval": 0,
            "period": 86400,
            "countdown": 0,
            "stop": None,
        }
    }
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _select_entity_id(hass, mock_config_entry_timers, "relay_aux1_period")
    state = hass.states.get(entity_id)
    assert state is not None
    # current_option resolves the seconds value back to its key.
    assert state.state == "1_day"
    # options list is the full PERIOD_MAP.
    assert "1_day" in state.attributes["options"]
    assert "1_week" in state.attributes["options"]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cell_boost_options_drop_active_redox_when_no_redox_module(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Without the Redox module flag, the cell-boost options drop 'active_redox'."""
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Redox measurement module detected": False,
    }
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _select_entity_id(hass, mock_config_entry_timers, "mbf_cell_boost")
    state = hass.states.get(entity_id)
    assert state is not None
    assert "active_redox" not in state.attributes["options"]


async def test_filtration_speed_packs_into_filtration_conf(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Selecting a speed delegates to the lib's async_set_filtration_speed."""
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _select_entity_id(
        hass, mock_config_entry_timers, "mbf_par_filtration_speed"
    )
    mock_neopool_client.async_set_filtration_speed.reset_mock()
    await _select_option(hass, entity_id, "high")
    mock_neopool_client.async_set_filtration_speed.assert_awaited_once_with("high")


async def test_filtration_speed_raises_when_not_manual_mode(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Changing filtration speed raises ServiceValidationError outside manual mode."""
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILT_MODE": 1,
    }
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _select_entity_id(
        hass, mock_config_entry_timers, "mbf_par_filtration_speed"
    )
    mock_neopool_client.async_set_filtration_speed.reset_mock()
    with pytest.raises(ServiceValidationError):
        await _select_option(hass, entity_id, "high")
    mock_neopool_client.async_set_filtration_speed.assert_not_awaited()


@pytest.mark.parametrize(
    ("speed_bits", "expected"),
    [
        (0x0000, "low"),
        (0x0010, "mid"),
        (0x0020, "high"),
    ],
)
async def test_filtration_speed_current_option_decodes_filtration_conf(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    speed_bits: int,
    expected: str,
) -> None:
    """Current option decodes bits 4-6 of MBF_PAR_FILTRATION_CONF to a speed label."""
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILTRATION_CONF": speed_bits | 0x0001,
    }
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _select_entity_id(
        hass, mock_config_entry_timers, "mbf_par_filtration_speed"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected


async def test_filtration_speed_timer_writes_per_timer_slot(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A per-timer speed select writes its own slot, not the live speed.

    Guards against the live-vs-timer slot mix-up: the entity must call
    async_set_filtration_speed_timer(1, ...), never async_set_filtration_speed.
    """
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _select_entity_id(hass, mock_config_entry_timers, "filtration1_speed")
    mock_neopool_client.async_set_filtration_speed.reset_mock()
    mock_neopool_client.async_set_filtration_speed_timer.reset_mock()
    await _select_option(hass, entity_id, "high")
    mock_neopool_client.async_set_filtration_speed_timer.assert_awaited_once_with(
        1, "high"
    )
    mock_neopool_client.async_set_filtration_speed.assert_not_awaited()


async def test_filtration_speed_timer_current_option_decodes_timer_slot(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Timer 1 decodes bits 7-9 of MBF_PAR_FILTRATION_CONF, not the live slot."""
    # Timer1 "high" (2) at shift 7 == 0x0100, live-speed slot left at low.
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILTRATION_CONF": 0x0100 | 0x0001,
    }
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _select_entity_id(hass, mock_config_entry_timers, "filtration1_speed")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "high"


async def test_timer_period_select_calls_set_timer_service(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A timer_period select forwards a period in seconds to set_timer."""
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(hass, mock_config_entry_timers, "relay_aux1_period")
    mock_neopool_client.write_timer.reset_mock()
    await _select_option(hass, entity_id, "1_week")
    timer_name, payload = mock_neopool_client.write_timer.await_args.args
    assert timer_name == "relay_aux1"
    assert payload["period"] == 604800


async def test_timer_period_no_repeat_writes_zero(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Selecting no_repeat writes a period of 0, returning the timer to run-once."""
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(hass, mock_config_entry_timers, "relay_aux1_period")
    mock_neopool_client.write_timer.reset_mock()
    await _select_option(hass, entity_id, "no_repeat")
    timer_name, payload = mock_neopool_client.write_timer.await_args.args
    assert timer_name == "relay_aux1"
    assert payload["period"] == 0


async def test_timer_period_off_map_value_surfaced_as_raw_seconds(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A non-zero period outside the canonical map shows as a raw-seconds option."""
    mock_neopool_client.read_all_timers.side_effect = None
    mock_neopool_client.read_all_timers.return_value = {
        "relay_aux1": {
            "enable": 4,
            "on": 0,
            "interval": 0,
            "period": 12345,
            "countdown": 0,
            "stop": None,
        }
    }
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _select_entity_id(hass, mock_config_entry_timers, "relay_aux1_period")
    state = hass.states.get(entity_id)
    assert state.state == "12345"
    assert "12345" in state.attributes["options"]
    assert "no_repeat" in state.attributes["options"]


async def test_timer_period_zero_reads_as_no_repeat(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A device period of 0 surfaces as no_repeat, which stays selectable."""
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(hass, mock_config_entry_timers, "relay_aux1_period")
    state = hass.states.get(entity_id)
    assert state.state == "no_repeat"
    assert "no_repeat" in state.attributes["options"]


async def test_timer_period_write_holds_block_lock(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """The period write runs under the block's timer_write_lock.

    write_timer rewrites the whole block, so it must be serialized against the
    time platform's start/stop writes on the same block.
    """
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(hass, mock_config_entry_timers, "relay_aux1_period")
    coordinator = mock_config_entry_timers.runtime_data

    locked_during_write = False

    async def _check_lock(_timer: str, _payload: dict) -> None:
        nonlocal locked_during_write
        locked_during_write = coordinator.timer_write_lock("relay_aux1").locked()

    mock_neopool_client.write_timer = AsyncMock(side_effect=_check_lock)
    await _select_option(hass, entity_id, "1_week")
    assert locked_during_write


async def test_relay_mode_select_switches_via_lib_api(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A relay_mode select delegates to the lib's async_set_relay_mode."""
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(hass, mock_config_entry_timers, "relay_aux1_mode")
    mock_neopool_client.async_set_relay_mode = AsyncMock(
        return_value={"relay_aux1_enable": 1, "AUX1": False},
    )
    await _select_option(hass, entity_id, "auto")
    mock_neopool_client.async_set_relay_mode.assert_awaited_once_with(
        RelayKind.AUX1, RelayMode.AUTO
    )
    assert hass.states.get(entity_id).state == "auto"


async def test_relay_mode_write_holds_block_lock(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """The relay-mode write runs under the block's timer_write_lock.

    async_set_relay_mode rewrites the whole block, so it must be serialized
    against the time and select platforms' writes on the same block.
    """
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(hass, mock_config_entry_timers, "relay_aux1_mode")
    coordinator = mock_config_entry_timers.runtime_data

    locked_during_write = False

    async def _check_lock(_relay: object, _mode: object) -> dict[str, object]:
        nonlocal locked_during_write
        locked_during_write = coordinator.timer_write_lock("relay_aux1").locked()
        return {}

    mock_neopool_client.async_set_relay_mode = AsyncMock(side_effect=_check_lock)
    await _select_option(hass, entity_id, "auto")
    assert locked_during_write


async def test_relay_mode_manual_to_manual_is_noop(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Selecting 'manual' when the relay already is in a manual state does not write."""
    mock_neopool_client.read_all_timers.side_effect = None
    mock_neopool_client.read_all_timers.return_value = {
        "relay_aux1": {
            "enable": 3,
            "on": 0,
            "interval": 0,
            "period": 0,
            "countdown": 0,
            "stop": None,
        }
    }
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _select_entity_id(hass, mock_config_entry_timers, "relay_aux1_mode")
    mock_neopool_client.async_set_relay_mode = AsyncMock(return_value={})
    await _select_option(hass, entity_id, "manual")
    mock_neopool_client.async_set_relay_mode.assert_not_awaited()


async def test_relay_mode_selecting_disabled_is_noop(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Selecting the read-only 'disabled' state does not write to the relay."""
    mock_neopool_client.read_all_timers.side_effect = None
    mock_neopool_client.read_all_timers.return_value = {
        "relay_aux1": {
            "enable": 0,
            "on": 0,
            "interval": 0,
            "period": 0,
            "countdown": 0,
            "stop": None,
        }
    }
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _select_entity_id(hass, mock_config_entry_timers, "relay_aux1_mode")
    assert "disabled" in hass.states.get(entity_id).attributes["options"]
    mock_neopool_client.async_set_relay_mode = AsyncMock(return_value={})
    await _select_option(hass, entity_id, "disabled")
    mock_neopool_client.async_set_relay_mode.assert_not_awaited()


async def test_timer_period_maps_communication_error_to_home_assistant_error(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A NeoPoolError from write_timer surfaces as a translated HomeAssistantError."""
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(hass, mock_config_entry_timers, "relay_aux1_period")
    mock_neopool_client.write_timer = AsyncMock(side_effect=NeoPoolError("boom"))
    with pytest.raises(HomeAssistantError):
        await _select_option(hass, entity_id, "1_week")


async def test_relay_mode_maps_communication_error_to_home_assistant_error(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A NeoPoolError from async_set_relay_mode surfaces as a translated HomeAssistantError."""
    await setup_integration(hass, mock_config_entry_timers)
    entity_id = _select_entity_id(hass, mock_config_entry_timers, "relay_aux1_mode")
    mock_neopool_client.async_set_relay_mode = AsyncMock(
        side_effect=NeoPoolError("boom"),
    )
    with pytest.raises(HomeAssistantError):
        await _select_option(hass, entity_id, "auto")


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_neopool_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry_timers: MockConfigEntry,
) -> None:
    """Snapshot every entity registered by the select platform."""
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry_timers)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_timers.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_when_modules_absent(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    minimal_pool_data: dict[str, Any],
) -> None:
    """Snapshot the select entities registered when no modules are present."""
    mock_neopool_client.async_read_all.return_value = minimal_pool_data
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry_timers)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_timers.entry_id
    )
