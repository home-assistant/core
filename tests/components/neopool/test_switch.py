"""Tests for the NeoPool switch platform."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from neopool_modbus import InvalidStateReason, NeoPoolInvalidStateError
from neopool_modbus.decoders import encode_cell_boost
from neopool_modbus.exceptions import NeoPoolConnectionError
from neopool_modbus.registers import (
    BinaryConfigFlag,
    BitmaskConfigFlag,
    FiltValveMode,
    RelayKind,
    TimerRelayMode,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.neopool.const import FOLLOW_UP_REFRESH_DELAY
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import MOCK_POOL_DATA

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def _turn_on(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": entity_id},
        blocking=True,
    )


async def _turn_off(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": entity_id},
        blocking=True,
    )


def _entity_id_by_suffix(
    hass: HomeAssistant, entry: MockConfigEntry, suffix: str
) -> str:
    """Resolve a switch entity_id by its unique_id suffix."""
    registry = er.async_get(hass)
    entries = [
        e
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.domain == SWITCH_DOMAIN and e.unique_id.endswith(suffix)
    ]
    assert entries, f"no switch entity with unique_id ending in {suffix}"
    return entries[0].entity_id


async def test_manual_filtration_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Manual filtration dispatches to async_set_manual_filtration(state)."""
    mock_neopool_client.async_set_manual_filtration.side_effect = lambda state: {
        "Filtration Pump": state,
        "MBF_PAR_FILT_MANUAL_STATE": int(state),
    }
    await setup_integration(hass, mock_config_entry)

    await _turn_on(hass, "switch.neopool_filtration")
    mock_neopool_client.async_set_manual_filtration.assert_called_with(True)

    mock_neopool_client.async_set_manual_filtration.reset_mock()
    await _turn_off(hass, "switch.neopool_filtration")
    mock_neopool_client.async_set_manual_filtration.assert_called_with(False)


async def test_manual_filtration_raises_when_not_manual_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """turn_on/off raises ServiceValidationError when filtration mode is not manual."""
    await setup_integration(hass, mock_config_entry)

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILT_MODE": 1,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_neopool_client.async_set_manual_filtration.reset_mock()
    with pytest.raises(ServiceValidationError) as exc:
        await _turn_on(hass, "switch.neopool_filtration")
    assert exc.value.translation_key == "filtration_not_manual_mode"
    with pytest.raises(ServiceValidationError):
        await _turn_off(hass, "switch.neopool_filtration")
    mock_neopool_client.async_set_manual_filtration.assert_not_called()


async def test_manual_filtration_raises_when_boost_active(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Manual mode but active boost: the pre-check must block the write."""
    await setup_integration(hass, mock_config_entry)

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILT_MODE": 0,
        "MBF_CELL_BOOST": encode_cell_boost("active"),
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_neopool_client.async_set_manual_filtration.reset_mock()
    with pytest.raises(ServiceValidationError) as exc:
        await _turn_on(hass, "switch.neopool_filtration")
    assert exc.value.translation_key == "filtration_boost_active"
    mock_neopool_client.async_set_manual_filtration.assert_not_called()


async def test_manual_filtration_is_on_reflects_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """is_on tracks the "Filtration Pump" relay state, regardless of mode."""
    await setup_integration(hass, mock_config_entry)

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILT_MODE": 1,
        "Filtration Pump": True,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("switch.neopool_filtration").state == STATE_ON

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILT_MODE": 1,
        "Filtration Pump": False,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("switch.neopool_filtration").state == STATE_OFF


async def test_filtration_maps_filtration_reason_to_dedicated_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A FILTRATION_NOT_IN_MANUAL_MODE reason routes to the filtration key.

    The cache says manual mode, so the pre-check passes, but the library
    rejects the write for a race where the device left manual since the poll.
    """
    await setup_integration(hass, mock_config_entry)

    mock_neopool_client.async_set_manual_filtration.side_effect = (
        NeoPoolInvalidStateError(
            "not in manual filtration mode",
            reason=InvalidStateReason.FILTRATION_NOT_IN_MANUAL_MODE,
        )
    )
    with pytest.raises(ServiceValidationError) as exc:
        await _turn_on(hass, "switch.neopool_filtration")
    assert exc.value.translation_key == "filtration_not_manual_mode"


@pytest.mark.parametrize(
    ("suffix", "flag"),
    [
        ("_mbf_par_clima_onoff", BinaryConfigFlag.CLIMA_ONOFF),
        ("_mbf_par_smart_anti_freeze", BinaryConfigFlag.SMART_ANTI_FREEZE),
        ("_mbf_par_uv_mode", BinaryConfigFlag.UV_MODE),
    ],
    ids=lambda v: v.name if isinstance(v, BinaryConfigFlag) else v,
)
async def test_binary_flag_switch_writes_flag(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    suffix: str,
    flag: BinaryConfigFlag,
) -> None:
    """The grouped switches dispatch to async_set_binary_flag with their flag."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _entity_id_by_suffix(hass, mock_config_entry, suffix)

    mock_neopool_client.async_set_binary_flag.reset_mock()
    await _turn_on(hass, entity_id)
    mock_neopool_client.async_set_binary_flag.assert_called_with(flag, True)

    mock_neopool_client.async_set_binary_flag.reset_mock()
    await _turn_off(hass, entity_id)
    mock_neopool_client.async_set_binary_flag.assert_called_with(flag, False)


async def test_hidro_cover_enable_bitmask_writes(
    hass: HomeAssistant,
    mock_config_entry_switch: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """The hydrolysis cover-enable bitmask switch dispatches to the bitmask API."""
    await setup_integration(hass, mock_config_entry_switch)
    entity_id = _entity_id_by_suffix(
        hass, mock_config_entry_switch, "_mbf_par_hidro_cover_enable"
    )

    mock_neopool_client.async_set_bitmask_flag.reset_mock()
    await _turn_on(hass, entity_id)
    mock_neopool_client.async_set_bitmask_flag.assert_called_with(
        BitmaskConfigFlag.HIDRO_COVER_ENABLE, True
    )

    mock_neopool_client.async_set_bitmask_flag.reset_mock()
    await _turn_off(hass, entity_id)
    mock_neopool_client.async_set_bitmask_flag.assert_called_with(
        BitmaskConfigFlag.HIDRO_COVER_ENABLE, False
    )


async def test_hidro_bitmask_switches_reflect_options_bitfield(
    hass: HomeAssistant,
    mock_config_entry_switch: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Both hidro switches read is_on from the shared MBF_PAR_HIDRO_COVER_ENABLE bitfield."""
    await setup_integration(hass, mock_config_entry_switch)
    cover_id = _entity_id_by_suffix(
        hass, mock_config_entry_switch, "_mbf_par_hidro_cover_enable"
    )
    shutdown_id = _entity_id_by_suffix(
        hass, mock_config_entry_switch, "_mbf_par_hidro_temp_shutdown"
    )
    assert hass.states.get(cover_id).state == STATE_OFF
    assert hass.states.get(shutdown_id).state == STATE_OFF

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_HIDRO_COVER_ENABLE": 0x0003,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(cover_id).state == STATE_ON
    assert hass.states.get(shutdown_id).state == STATE_ON


async def test_aux_relay_turn_on_off_writes_relay_state(
    hass: HomeAssistant,
    mock_config_entry_switch: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """aux1 turn_on/off dispatches to async_set_relay_state(RelayKind.AUX1, state)."""
    mock_neopool_client.async_set_relay_state.side_effect = lambda relay, state: {
        "AUX1": state
    }
    await setup_integration(hass, mock_config_entry_switch)
    entity_id = _entity_id_by_suffix(hass, mock_config_entry_switch, "_aux1")

    mock_neopool_client.async_set_relay_state.reset_mock()
    await _turn_on(hass, entity_id)
    mock_neopool_client.async_set_relay_state.assert_called_with(RelayKind.AUX1, True)

    mock_neopool_client.async_set_relay_state.reset_mock()
    await _turn_off(hass, entity_id)
    mock_neopool_client.async_set_relay_state.assert_called_with(RelayKind.AUX1, False)


@pytest.mark.parametrize(
    ("aux_suffix", "block"),
    [
        ("_aux1", "relay_aux1"),
        ("_aux2", "relay_aux2"),
        ("_aux3", "relay_aux3"),
        ("_aux4", "relay_aux4"),
    ],
)
@pytest.mark.parametrize(
    "enable_value",
    [
        pytest.param(TimerRelayMode.ENABLED, id="auto"),
        pytest.param(None, id="missing"),
        pytest.param(0, id="disabled"),
        pytest.param(2, id="unknown-state"),
    ],
)
async def test_aux_relay_refuses_when_not_in_manual_mode(
    hass: HomeAssistant,
    mock_config_entry_switch: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    aux_suffix: str,
    block: str,
    enable_value: int | None,
) -> None:
    """Aux relay refuses to fire unless the relay is in a manual mode."""

    def _timers(
        enabled_timers: list[str] | None = None, **_kwargs: Any
    ) -> dict[str, dict[str, Any]]:
        if enable_value is None:
            return {}
        return {
            block: {
                "enable": enable_value,
                "on": 0,
                "interval": 0,
                "period": 0,
                "countdown": 0,
                "stop": None,
            }
        }

    mock_neopool_client.read_all_timers.side_effect = _timers
    await setup_integration(hass, mock_config_entry_switch)
    entity_id = _entity_id_by_suffix(hass, mock_config_entry_switch, aux_suffix)

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_neopool_client.async_set_relay_state.reset_mock()
    with pytest.raises(ServiceValidationError):
        await _turn_on(hass, entity_id)
    with pytest.raises(ServiceValidationError):
        await _turn_off(hass, entity_id)
    mock_neopool_client.async_set_relay_state.assert_not_called()


async def test_aux_relay_maps_lib_invalid_state_to_service_validation(
    hass: HomeAssistant,
    mock_config_entry_switch: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Race window: cache guard passes but the library refuses on write."""
    await setup_integration(hass, mock_config_entry_switch)
    entity_id = _entity_id_by_suffix(hass, mock_config_entry_switch, "_aux1")

    mock_neopool_client.async_set_relay_state.side_effect = NeoPoolInvalidStateError(
        "relay in auto mode",
        reason=InvalidStateReason.RELAY_IN_AUTO_MODE,
    )
    with pytest.raises(ServiceValidationError) as exc:
        await _turn_on(hass, entity_id)
    assert exc.value.translation_key == "relay_in_auto_mode"


@pytest.mark.parametrize(
    "write_error",
    [
        pytest.param(NeoPoolConnectionError("boom"), id="lib-connection-error"),
        pytest.param(TimeoutError("boom"), id="timeout"),
        pytest.param(OSError("boom"), id="os-error"),
    ],
)
async def test_aux_relay_maps_communication_error_to_home_assistant_error(
    hass: HomeAssistant,
    mock_config_entry_switch: MockConfigEntry,
    mock_neopool_client: MagicMock,
    write_error: Exception,
) -> None:
    """Communication errors on write are surfaced as translated HomeAssistantError."""
    await setup_integration(hass, mock_config_entry_switch)
    entity_id = _entity_id_by_suffix(hass, mock_config_entry_switch, "_aux1")

    mock_neopool_client.async_set_relay_state.side_effect = write_error
    with pytest.raises(HomeAssistantError):
        await _turn_on(hass, entity_id)


async def test_backwash_turn_on_starts_and_reports_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """turn_on starts the backwash and reports ON once the device confirms."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _entity_id_by_suffix(hass, mock_config_entry, "_backwash")

    mock_neopool_client.async_start_backwash.reset_mock()
    await _turn_on(hass, entity_id)
    mock_neopool_client.async_start_backwash.assert_awaited_once_with()

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILTVALVE_REMAINING": 150,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON


async def test_backwash_turn_off_stops_and_reports_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """turn_off stops the backwash and reports OFF once the device confirms."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _entity_id_by_suffix(hass, mock_config_entry, "_backwash")

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILTVALVE_REMAINING": 120,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    mock_neopool_client.async_stop_backwash.reset_mock()
    await _turn_off(hass, entity_id)
    mock_neopool_client.async_stop_backwash.assert_awaited_once_with()

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILTVALVE_REMAINING": 0,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF


async def test_backwash_turn_on_raises_when_interval_unset(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """turn_on with no configured duration raises before touching the client."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _entity_id_by_suffix(hass, mock_config_entry, "_backwash")

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILTVALVE_INTERVAL": 0,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_neopool_client.async_start_backwash.reset_mock()
    with pytest.raises(ServiceValidationError) as exc:
        await _turn_on(hass, entity_id)
    assert exc.value.translation_key == "filtvalve_interval_not_set"
    mock_neopool_client.async_start_backwash.assert_not_called()


async def test_backwash_is_on_tracks_remaining_countdown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """is_on follows MBF_PAR_FILTVALVE_REMAINING, so it clears when the cycle ends."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _entity_id_by_suffix(hass, mock_config_entry, "_backwash")

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILTVALVE_REMAINING": 90,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILTVALVE_REMAINING": 0,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_backwash_maps_lib_invalid_state_to_service_validation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Fail-safe: interval present in cache but the library rejects with a reason."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _entity_id_by_suffix(hass, mock_config_entry, "_backwash")

    mock_neopool_client.async_start_backwash.side_effect = NeoPoolInvalidStateError(
        "no interval",
        reason=InvalidStateReason.FILTVALVE_INTERVAL_NOT_SET,
    )
    with pytest.raises(ServiceValidationError) as exc:
        await _turn_on(hass, entity_id)
    assert exc.value.translation_key == "filtvalve_interval_not_set"


@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_backwash_raises_when_valve_in_auto(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    service: str,
) -> None:
    """Toggling with the valve in AUTO mode raises before touching the client."""
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILTVALVE_MODE": FiltValveMode.AUTO.value,
    }
    await setup_integration(hass, mock_config_entry)
    entity_id = _entity_id_by_suffix(hass, mock_config_entry, "_backwash")

    mock_neopool_client.async_start_backwash.reset_mock()
    mock_neopool_client.async_stop_backwash.reset_mock()
    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            SWITCH_DOMAIN, service, {"entity_id": entity_id}, blocking=True
        )
    assert exc.value.translation_key == "filtvalve_in_auto_mode"
    mock_neopool_client.async_start_backwash.assert_not_called()
    mock_neopool_client.async_stop_backwash.assert_not_called()


async def test_backwash_absent_without_filtvalve(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """No backwash switch is registered when the filter valve is absent."""
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILTVALVE_GPIO": 0,
        "MBF_PAR_FILTVALVE_ENABLE": 0,
    }
    await setup_integration(hass, mock_config_entry)

    matches = [
        e
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if e.domain == SWITCH_DOMAIN and e.unique_id.endswith("_backwash")
    ]
    assert matches == []


async def test_manual_filtration_absent_without_filt_gpio(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """No manual filtration switch is registered when no filtration relay exists."""
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILT_GPIO": 0,
    }
    await setup_integration(hass, mock_config_entry)

    matches = [
        e
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if e.domain == SWITCH_DOMAIN
        and e.unique_id.endswith("_mbf_par_filt_manual_state")
    ]
    assert matches == []


@pytest.mark.usefixtures("mock_neopool_client")
async def test_aux_and_cover_absent_when_options_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No aux or cover switches are created while their options are off."""
    await setup_integration(hass, mock_config_entry)
    gated = [
        e
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if e.domain == SWITCH_DOMAIN
        and (
            e.unique_id.endswith(("_aux1", "_aux2", "_aux3", "_aux4"))
            or e.unique_id.endswith("_mbf_par_hidro_cover_enable")
        )
    ]
    assert gated == []


async def test_switch_write_schedules_follow_up_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A successful write triggers a second refresh after the follow-up delay."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _entity_id_by_suffix(hass, mock_config_entry, "_mbf_par_clima_onoff")

    reads_before = mock_neopool_client.async_read_all.await_count
    await _turn_on(hass, entity_id)

    freezer.tick(timedelta(seconds=FOLLOW_UP_REFRESH_DELAY + 0.5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_neopool_client.async_read_all.await_count > reads_before


@pytest.mark.usefixtures("mock_neopool_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry_switch: MockConfigEntry,
) -> None:
    """Snapshot every switch entity registered by the platform."""
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry_switch)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_switch.entry_id
    )
