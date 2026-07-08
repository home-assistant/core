"""Tests for the NeoPool light platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from neopool_modbus import NeoPoolInvalidStateError
from neopool_modbus.registers import RelayKind, TimerRelayMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import MOCK_POOL_DATA

from tests.common import MockConfigEntry, async_fire_time_changed


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
        if e.domain == "light"
    ]
    assert entries, "expected exactly one neopool light entity"
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
    coordinator = mock_config_entry_light.runtime_data
    assert coordinator.data.get("Pool Light") is True

    mock_neopool_client.async_set_relay_state = AsyncMock(
        return_value={"Pool Light": False}
    )
    await _turn_off(hass, entity_id)
    mock_neopool_client.async_set_relay_state.assert_awaited_once_with(
        RelayKind.LIGHT, False
    )
    assert coordinator.data.get("Pool Light") is False


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
    "enable_value",
    [
        pytest.param(TimerRelayMode.ENABLED, id="auto"),
        pytest.param(None, id="missing"),
        pytest.param(0, id="disabled"),
        pytest.param(2, id="unknown-state"),
    ],
)
async def test_light_refuses_when_not_in_manual_mode(
    hass: HomeAssistant,
    mock_config_entry_light: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    enable_value: int | None,
) -> None:
    """Turn on/off is rejected while the relay is not in a manual mode."""
    await setup_integration(hass, mock_config_entry_light)
    entity_id = _light_entity_id(hass, mock_config_entry_light)

    data = {**MOCK_POOL_DATA}
    if enable_value is None:
        data.pop("relay_light_enable", None)
    else:
        data["relay_light_enable"] = enable_value
    mock_neopool_client.async_read_all.return_value = data
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
        if e.domain == "light"
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
        if e.domain == "light"
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
    entries = sorted(
        er.async_entries_for_config_entry(
            entity_registry, mock_config_entry_light.entry_id
        ),
        key=lambda e: e.entity_id,
    )
    assert entries == snapshot
