"""Test Gardena Bluetooth valve."""

from collections.abc import Awaitable, Callable
from unittest.mock import Mock, call

from gardena_bluetooth.const import Valve, Valve1, Valve2, ValveX
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    Platform,
)
from homeassistant.core import HomeAssistant
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

    entity_id = "valve.mock_title"
    await setup_entry(hass, mock_entry, [Platform.VALVE])
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

    entity_id = "valve.mock_title"
    await setup_entry(hass, mock_entry, [Platform.VALVE])
    assert hass.states.get(entity_id)

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_OPEN_VALVE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_CLOSE_VALVE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_client.write_char.mock_calls == [
        call(Valve.remaining_open_time, 1000),
        call(Valve.remaining_open_time, 0),
    ]


@pytest.fixture
def mock_dual_valvex_chars(mock_read_char_raw: dict[str, bytes]) -> dict[str, bytes]:
    """Mock both Valve1 and Valve2 chars for a G-19034 dual-valve device."""
    for service in (Valve1, Valve2):
        mock_read_char_raw[service.state.uuid] = b"\x00"
        mock_read_char_raw[service.available.uuid] = b"\x01"
        mock_read_char_raw[service.remaining_time_open.uuid] = (
            service.remaining_time_open.encode(0)
        )
        mock_read_char_raw[service.manual_watering_duration.uuid] = (
            service.manual_watering_duration.encode(1800)
        )
        mock_read_char_raw[service.activation_reason.uuid] = b"\x00"
        mock_read_char_raw[service.start_watering.uuid] = b""
        mock_read_char_raw[service.stop_watering.uuid] = b""
    return mock_read_char_raw


async def test_valvex_dual_both_entities_created(
    hass: HomeAssistant,
    mock_client: Mock,
    mock_dual_valvex_chars: dict[str, bytes],
) -> None:
    """Both Valve1 and Valve2 entities are created when all characteristics are present."""
    mock_entry = get_config_entry(SMART_DUAL_WATER_CONTROL_SERVICE_INFO)
    await setup_entry(
        hass,
        mock_entry,
        [Platform.VALVE],
        service_info=SMART_DUAL_WATER_CONTROL_SERVICE_INFO,
    )

    valve_states = [s for s in hass.states.async_all() if s.domain == "valve"]
    assert len(valve_states) == 2


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
async def test_valvex_switching(
    hass: HomeAssistant,
    mock_client: Mock,
    mock_valvex_chars: dict[str, bytes],
    service_info: BluetoothServiceInfo,
    service: type[ValveX],
) -> None:
    """Open/close on the Smart Water Control family writes the LWM2M payload."""

    mock_entry = get_config_entry(service_info)
    await setup_entry(hass, mock_entry, [Platform.VALVE], service_info=service_info)

    valve_states = [s for s in hass.states.async_all() if s.domain == "valve"]
    assert len(valve_states) == 1
    entity_id = valve_states[0].entity_id

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_OPEN_VALVE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_CLOSE_VALVE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_client.write_char.mock_calls == [
        call(service.start_watering, {0: "18", 1: "1800"}),
        call(service.stop_watering, {0: "18"}),
    ]
