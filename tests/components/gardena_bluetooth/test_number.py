"""Test Gardena Bluetooth sensor."""


from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import Mock, call

from gardena_bluetooth.const import Valve
from gardena_bluetooth.exceptions import (
    CharacteristicNoAccess,
    GardenaBluetoothException,
)
from gardena_bluetooth.parse import Characteristic
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    Platform,
)
from homeassistant.core import HomeAssistant

from . import setup_entry

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("uuid", "raw", "entity_id"),
    [
        (
            Valve.manual_watering_time.uuid,
            [
                Valve.manual_watering_time.encode(100),
                Valve.manual_watering_time.encode(10),
            ],
            "number.mock_title_manual_watering_time",
        ),
        (
            Valve.remaining_open_time.uuid,
            [
                Valve.remaining_open_time.encode(100),
                Valve.remaining_open_time.encode(10),
                CharacteristicNoAccess("Test for no access"),
                GardenaBluetoothException("Test for errors on bluetooth"),
            ],
            "number.mock_title_remaining_open_time",
        ),
        (
            Valve.remaining_open_time.uuid,
            [Valve.remaining_open_time.encode(100)],
            "number.mock_title_open_for",
        ),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_read_char_raw: dict[str, bytes],
    scan_step: Callable[[], Awaitable[None]],
    uuid: str,
    raw: list[bytes],
    entity_id: str,
) -> None:
    """Test setup creates expected entities."""

    mock_read_char_raw[uuid] = raw[0]
    await setup_entry(hass, mock_entry, [Platform.NUMBER])
    assert hass.states.get(entity_id) == snapshot

    for char_raw in raw[1:]:
        mock_read_char_raw[uuid] = char_raw
        await scan_step()
        assert hass.states.get(entity_id) == snapshot


@pytest.mark.parametrize(
    ("char", "value", "expected", "entity_id"),
    [
        (
            Valve.manual_watering_time,
            100,
            100,
            "number.mock_title_manual_watering_time",
        ),
        (
            Valve.remaining_open_time,
            100,
            100 * 60,
            "number.mock_title_open_for",
        ),
    ],
)
async def test_config(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_read_char_raw: dict[str, bytes],
    mock_client: Mock,
    char: Characteristic,
    value: Any,
    expected: Any,
    entity_id: str,
) -> None:
    """Test setup creates expected entities."""

    mock_read_char_raw[char.uuid] = char.encode(value)
    await setup_entry(hass, mock_entry, [Platform.NUMBER])
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

    mock_read_char_raw[
        Valve.manual_watering_time.uuid
    ] = Valve.manual_watering_time.encode(0)
    mock_read_char_raw[
        Valve.remaining_open_time.uuid
    ] = Valve.remaining_open_time.encode(0)

    await setup_entry(hass, mock_entry, [Platform.NUMBER])
    assert hass.states.get("number.mock_title_remaining_open_time") == snapshot
    assert hass.states.get("number.mock_title_manual_watering_time") == snapshot

    mock_read_char_raw[Valve.manual_watering_time.uuid] = GardenaBluetoothException(
        "Test for errors on bluetooth"
    )

    await scan_step()
    assert hass.states.get("number.mock_title_remaining_open_time") == snapshot
    assert hass.states.get("number.mock_title_manual_watering_time") == snapshot
