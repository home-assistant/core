"""Test Gardena Bluetooth sensor."""

from collections.abc import Awaitable, Callable
from unittest.mock import Mock, call

from gardena_bluetooth.const import Valve, Valve1, Valve2, ValveX
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import (
    SMART_DUAL_WATER_CONTROL_SERVICE_INFO,
    SMART_WATER_CONTROL_SERVICE_INFO,
    get_config_entry,
    setup_entry,
)

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("constant_advertisements")


@pytest.fixture
def mock_switch_chars(mock_read_char_raw):
    """Mock data on device."""
    mock_read_char_raw[Valve.state.uuid] = b"\x00"
    mock_read_char_raw[Valve.remaining_open_time.uuid] = (
        Valve.remaining_open_time.encode(0)
    )
    mock_read_char_raw[Valve.manual_watering_time.uuid] = (
        Valve.manual_watering_time.encode(1000)
    )
    return mock_read_char_raw


async def test_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    mock_switch_chars: dict[str, bytes],
    scan_step: Callable[[], Awaitable[None]],
) -> None:
    """Test setup creates expected entities."""

    entity_id = "switch.mock_title_open"
    await setup_entry(hass, mock_entry, [Platform.SWITCH])
    assert hass.states.get(entity_id) == snapshot

    mock_switch_chars[Valve.state.uuid] = b"\x01"
    await scan_step()
    assert hass.states.get(entity_id) == snapshot


async def test_switching(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    mock_switch_chars: dict[str, bytes],
) -> None:
    """Test switching makes correct calls."""

    entity_id = "switch.mock_title_open"
    await setup_entry(hass, mock_entry, [Platform.SWITCH])
    assert hass.states.get(entity_id)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_client.write_char.mock_calls == [
        call(Valve.remaining_open_time, 1000),
        call(Valve.remaining_open_time, 0),
    ]


@pytest.mark.parametrize(
    ("mock_valvex_chars", "service_info", "service"),
    [
        pytest.param(
            Valve1,
            SMART_WATER_CONTROL_SERVICE_INFO,
            Valve1,
            id="wc_single_G-19033",
        ),
        pytest.param(
            Valve2,
            SMART_DUAL_WATER_CONTROL_SERVICE_INFO,
            Valve2,
            id="wc_dual_G-19034_valve2",
        ),
    ],
    indirect=["mock_valvex_chars"],
)
async def test_valvex_switch_alias(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: Mock,
    mock_valvex_chars: dict[str, bytes],
    service_info: BluetoothServiceInfo,
    service: type[ValveX],
) -> None:
    """The Smart Water Control switch alias writes the LWM2M payload when enabled."""

    mock_entry = get_config_entry(service_info)
    await setup_entry(hass, mock_entry, [Platform.SWITCH], service_info=service_info)

    switch_entries = [
        e
        for e in er.async_entries_for_config_entry(entity_registry, mock_entry.entry_id)
        if e.domain == "switch"
    ]
    assert len(switch_entries) == 1
    entity_id = switch_entries[0].entity_id
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_client.write_char.mock_calls == [
        call(service.start_watering, {0: "18", 1: "1800"}),
        call(service.stop_watering, {0: "18"}),
    ]
