"""Tests for the NeoPool light platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from neopool_modbus import NeoPoolInvalidStateError
from neopool_modbus.exceptions import NeoPoolConnectionError
from neopool_modbus.registers import RelayKind, TimerRelayMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.neopool.const import FOLLOW_UP_REFRESH_DELAY
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


@pytest.fixture(autouse=True)
def _seed_light_relay_manual(mock_neopool_client: MagicMock) -> None:
    """Default the light relay timer to a manual mode so writes pass the guard."""
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "relay_light_enable": TimerRelayMode.ALWAYS_OFF,
        "Pool Light": False,
    }


async def _turn_on(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": entity_id},
        blocking=True,
    )


async def _turn_off(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": entity_id},
        blocking=True,
    )


def _light_entity_id(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    registry = er.async_get(hass)
    entries = [
        e
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.domain == LIGHT_DOMAIN
    ]
    assert len(entries) == 1, "expected exactly one neopool light entity"
    return entries[0].entity_id


async def test_light_turn_on_off_writes_via_relay_state(
    hass: HomeAssistant,
    mock_config_entry_light: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Light on/off delegates to the high-level async_set_relay_state API."""
    await setup_integration(hass, mock_config_entry_light)
    entity_id = _light_entity_id(hass, mock_config_entry_light)

    mock_neopool_client.async_set_relay_state = AsyncMock(
        return_value={"Pool Light": True}
    )
    await _turn_on(hass, entity_id)
    mock_neopool_client.async_set_relay_state.assert_awaited_once_with(
        RelayKind.LIGHT, True
    )
    assert hass.states.get(entity_id).state == STATE_ON

    mock_neopool_client.async_set_relay_state = AsyncMock(
        return_value={"Pool Light": False}
    )
    await _turn_off(hass, entity_id)
    mock_neopool_client.async_set_relay_state.assert_awaited_once_with(
        RelayKind.LIGHT, False
    )
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_light_is_on_reflects_relay_state(
    hass: HomeAssistant,
    mock_config_entry_light: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """is_on tracks the "Pool Light" relay state key from a fresh poll."""
    await setup_integration(hass, mock_config_entry_light)
    entity_id = _light_entity_id(hass, mock_config_entry_light)

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "relay_light_enable": TimerRelayMode.ALWAYS_ON,
        "Pool Light": True,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "relay_light_enable": TimerRelayMode.ALWAYS_OFF,
        "Pool Light": False,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF


@pytest.mark.parametrize(
    "relay_data",
    [
        pytest.param({"relay_light_enable": TimerRelayMode.ENABLED}, id="auto"),
        pytest.param({}, id="missing"),
        pytest.param({"relay_light_enable": 0}, id="disabled"),
        pytest.param({"relay_light_enable": 2}, id="unknown-state"),
    ],
)
async def test_light_refuses_when_not_in_manual_mode(
    hass: HomeAssistant,
    mock_config_entry_light: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    relay_data: dict[str, int],
) -> None:
    """Turn on/off is rejected while the relay is not in a manual mode."""
    await setup_integration(hass, mock_config_entry_light)
    entity_id = _light_entity_id(hass, mock_config_entry_light)

    mock_neopool_client.async_read_all.return_value = {**MOCK_POOL_DATA, **relay_data}
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_neopool_client.async_set_relay_state.reset_mock()
    with pytest.raises(ServiceValidationError):
        await _turn_on(hass, entity_id)
    with pytest.raises(ServiceValidationError):
        await _turn_off(hass, entity_id)
    mock_neopool_client.async_set_relay_state.assert_not_called()


async def test_light_maps_lib_invalid_state_to_service_validation(
    hass: HomeAssistant,
    mock_config_entry_light: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Lib-raised NeoPoolInvalidStateError is remapped to ServiceValidationError.

    Coordinator data may briefly lag the device state, so the pre-check passes
    but the library refuses. The mapping surfaces a translated error to users
    instead of leaking the raw library exception.
    """
    await setup_integration(hass, mock_config_entry_light)
    entity_id = _light_entity_id(hass, mock_config_entry_light)

    mock_neopool_client.async_set_relay_state = AsyncMock(
        side_effect=NeoPoolInvalidStateError("relay in auto mode")
    )
    with pytest.raises(ServiceValidationError):
        await _turn_on(hass, entity_id)
    mock_neopool_client.async_set_relay_state.assert_awaited_once_with(
        RelayKind.LIGHT, True
    )


@pytest.mark.parametrize(
    "write_error",
    [
        pytest.param(NeoPoolConnectionError("boom"), id="lib-connection-error"),
        pytest.param(TimeoutError("boom"), id="timeout"),
        pytest.param(OSError("boom"), id="os-error"),
    ],
)
async def test_light_maps_communication_error_to_home_assistant_error(
    hass: HomeAssistant,
    mock_config_entry_light: MockConfigEntry,
    mock_neopool_client: MagicMock,
    write_error: Exception,
) -> None:
    """Communication errors on write are surfaced as translated HomeAssistantError."""
    await setup_integration(hass, mock_config_entry_light)
    entity_id = _light_entity_id(hass, mock_config_entry_light)

    mock_neopool_client.async_set_relay_state = AsyncMock(side_effect=write_error)
    with pytest.raises(HomeAssistantError):
        await _turn_on(hass, entity_id)
    mock_neopool_client.async_set_relay_state.assert_awaited_once_with(
        RelayKind.LIGHT, True
    )


@pytest.mark.usefixtures("mock_neopool_client")
async def test_light_absent_when_option_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No light entity is created while the use_light option is off."""
    await setup_integration(hass, mock_config_entry)
    registry = er.async_get(hass)
    light_entries = [
        e
        for e in er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
        if e.domain == LIGHT_DOMAIN
    ]
    assert light_entries == []


async def test_light_absent_when_gpio_unassigned(
    hass: HomeAssistant,
    mock_config_entry_light: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Light entity is not registered when the lighting GPIO is unassigned."""
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_LIGHTING_GPIO": 0,
        "relay_light_enable": TimerRelayMode.ALWAYS_OFF,
    }
    await setup_integration(hass, mock_config_entry_light)
    registry = er.async_get(hass)
    light_entries = [
        e
        for e in er.async_entries_for_config_entry(
            registry, mock_config_entry_light.entry_id
        )
        if e.domain == LIGHT_DOMAIN
    ]
    assert light_entries == []


@pytest.mark.usefixtures("mock_neopool_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry_light: MockConfigEntry,
) -> None:
    """Snapshot every light entity registered by the platform."""
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry_light)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_light.entry_id
    )


async def test_light_write_schedules_follow_up_refresh(
    hass: HomeAssistant,
    mock_config_entry_light: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A successful write triggers a second refresh after the follow-up delay."""
    await setup_integration(hass, mock_config_entry_light)
    entity_id = _light_entity_id(hass, mock_config_entry_light)

    mock_neopool_client.async_set_relay_state = AsyncMock(
        return_value={"Pool Light": True}
    )
    reads_before = mock_neopool_client.async_read_all.await_count
    await _turn_on(hass, entity_id)

    freezer.tick(timedelta(seconds=FOLLOW_UP_REFRESH_DELAY + 0.5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_neopool_client.async_read_all.await_count > reads_before


async def test_light_timer_data_merged_into_coordinator(
    hass: HomeAssistant,
    mock_config_entry_light: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """The timer enable field is merged into coordinator data as relay_light_enable."""
    # Differ from the seeded ALWAYS_OFF so the assertion catches a missing merge.
    mock_neopool_client.read_all_timers = AsyncMock(
        return_value={
            "relay_light": {
                "enable": TimerRelayMode.ALWAYS_ON,
                "on": 3600,
                "interval": 7200,
                "period": 86400,
                "countdown": 120,
                "stop": 5400,
            }
        }
    )
    await setup_integration(hass, mock_config_entry_light)

    coordinator = mock_config_entry_light.runtime_data
    assert coordinator.data["relay_light_enable"] == TimerRelayMode.ALWAYS_ON
