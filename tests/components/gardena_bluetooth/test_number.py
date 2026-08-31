"""Test Gardena Bluetooth sensor."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import Mock, call

from gardena_bluetooth.const import AquaContourWatering, Sensor, Spray, Valve
from gardena_bluetooth.exceptions import (
    CharacteristicNoAccess,
    GardenaBluetoothException,
)
from gardena_bluetooth.parse import Characteristic
from habluetooth import BluetoothServiceInfo
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from . import AQUA_CONTOUR_SERVICE_INFO, WATER_TIMER_SERVICE_INFO, setup_entry

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("constant_advertisements")


@pytest.mark.parametrize(
    ("service_info", "unique_id", "raw", "entity_id"),
    [
        (
            WATER_TIMER_SERVICE_INFO,
            Valve.manual_watering_time.unique_id,
            [
                Valve.manual_watering_time.encode(100),
                Valve.manual_watering_time.encode(10),
            ],
            "number.mock_title_manual_watering_time",
        ),
        (
            WATER_TIMER_SERVICE_INFO,
            Valve.remaining_open_time.unique_id,
            [
                Valve.remaining_open_time.encode(100),
                Valve.remaining_open_time.encode(10),
                CharacteristicNoAccess("Test for no access"),
                GardenaBluetoothException("Test for errors on bluetooth"),
            ],
            "number.mock_title_remaining_open_time",
        ),
        (
            WATER_TIMER_SERVICE_INFO,
            Valve.remaining_open_time.unique_id,
            [Valve.remaining_open_time.encode(100)],
            "number.mock_title_open_for",
        ),
        (
            AQUA_CONTOUR_SERVICE_INFO,
            AquaContourWatering.manual_watering_time.unique_id,
            [
                AquaContourWatering.manual_watering_time.encode(100),
                AquaContourWatering.manual_watering_time.encode(10),
            ],
            "number.mock_title_manual_watering_time",
        ),
        (
            AQUA_CONTOUR_SERVICE_INFO,
            Spray.sector.unique_id,
            [
                Spray.sector.encode(359),
                Spray.sector.encode(10),
            ],
            "number.mock_title_sector",
        ),
        (
            AQUA_CONTOUR_SERVICE_INFO,
            Spray.distance.unique_id,
            [
                Spray.distance.encode(1000),
                Spray.distance.encode(10),
            ],
            "number.mock_title_distance",
        ),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_read_char_raw: dict[str, bytes],
    scan_step: Callable[[], Awaitable[None]],
    service_info: BluetoothServiceInfo,
    unique_id: str,
    raw: list[bytes],
    entity_id: str,
) -> None:
    """Test setup creates expected entities."""

    mock_read_char_raw[unique_id] = raw[0]
    await setup_entry(hass, platforms=[Platform.NUMBER], service_info=service_info)
    assert hass.states.get(entity_id) == snapshot

    for char_raw in raw[1:]:
        mock_read_char_raw[unique_id] = char_raw
        await scan_step()
        assert hass.states.get(entity_id) == snapshot


@pytest.mark.parametrize(
    ("service_info", "char", "value", "expected", "entity_id"),
    [
        (
            WATER_TIMER_SERVICE_INFO,
            Valve.manual_watering_time,
            100,
            100,
            "number.mock_title_manual_watering_time",
        ),
        (
            WATER_TIMER_SERVICE_INFO,
            Valve.remaining_open_time,
            100,
            100 * 60,
            "number.mock_title_open_for",
        ),
        (
            AQUA_CONTOUR_SERVICE_INFO,
            AquaContourWatering.manual_watering_time,
            100,
            100,
            "number.mock_title_manual_watering_time",
        ),
    ],
)
async def test_config(
    hass: HomeAssistant,
    mock_read_char_raw: dict[str, bytes],
    mock_client: Mock,
    service_info: BluetoothServiceInfo,
    char: Characteristic,
    value: Any,
    expected: Any,
    entity_id: str,
) -> None:
    """Test setup creates expected entities."""

    mock_read_char_raw[char.unique_id] = char.encode(value)
    await setup_entry(hass, platforms=[Platform.NUMBER], service_info=service_info)
    assert hass.states.get(entity_id)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    assert mock_client.write_char.mock_calls == [
        call(char, expected),
    ]


async def test_bluetooth_error_unavailable(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_read_char_raw: dict[str, bytes],
    scan_step: Callable[[], Awaitable[None]],
) -> None:
    """Verify that a connectivity error makes all entities unavailable."""

    mock_read_char_raw[Valve.manual_watering_time.unique_id] = (
        Valve.manual_watering_time.encode(0)
    )
    mock_read_char_raw[Valve.remaining_open_time.unique_id] = (
        Valve.remaining_open_time.encode(0)
    )

    await setup_entry(hass, mock_entry, [Platform.NUMBER])
    assert hass.states.get("number.mock_title_remaining_open_time") == snapshot
    assert hass.states.get("number.mock_title_manual_watering_time") == snapshot

    mock_read_char_raw[Valve.manual_watering_time.unique_id] = (
        GardenaBluetoothException("Test for errors on bluetooth")
    )

    await scan_step()
    assert hass.states.get("number.mock_title_remaining_open_time") == snapshot
    assert hass.states.get("number.mock_title_manual_watering_time") == snapshot


async def test_missing_connected_state(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_read_char_raw: dict[str, bytes],
    scan_step: Callable[[], Awaitable[None]],
) -> None:
    """Verify a device lacking the connected state characteristic stays usable.

    Entities are created on their primary characteristic alone, so their context
    can name a connected state the device does not expose.
    """

    mock_read_char_raw[Sensor.threshold.unique_id] = Sensor.threshold.encode(45)

    await setup_entry(hass, mock_entry, [Platform.NUMBER])
    await scan_step()

    # The primary characteristic still reports, so the entity stays available.
    state = hass.states.get("number.mock_title_sensor_threshold")
    assert state
    assert state.state == "45.0"


async def test_connected_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_read_char_raw: dict[str, bytes],
    scan_step: Callable[[], Awaitable[None]],
) -> None:
    """Verify that a connectivity error makes all entities unavailable."""

    mock_read_char_raw[Sensor.connected_state.unique_id] = (
        Sensor.connected_state.encode(False)
    )
    mock_read_char_raw[Sensor.threshold.unique_id] = Sensor.threshold.encode(45)

    await setup_entry(hass, mock_entry, [Platform.NUMBER])
    assert hass.states.get("number.mock_title_sensor_threshold") == snapshot

    mock_read_char_raw[Sensor.connected_state.unique_id] = (
        Sensor.connected_state.encode(True)
    )

    await scan_step()
    assert hass.states.get("number.mock_title_sensor_threshold") == snapshot
