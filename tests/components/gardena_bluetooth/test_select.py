"""Test Gardena Bluetooth sensor."""

from collections.abc import Awaitable, Callable
from unittest.mock import Mock, call

from gardena_bluetooth.const import (
    AquaContour,
    AquaContourPosition,
    AquaContourWatering,
    AquaContourWateringMode,
)
from habluetooth import BluetoothServiceInfo
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import AQUA_CONTOUR_SERVICE_INFO, setup_entry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def mock_chars(mock_read_char_raw):
    """Mock data on device."""
    mock_read_char_raw[AquaContourWatering.watering_active.uuid] = b"\x00"
    return mock_read_char_raw


@pytest.mark.parametrize(
    ("service_info", "raw"),
    [
        pytest.param(
            AQUA_CONTOUR_SERVICE_INFO,
            {
                AquaContourWatering.watering_active.uuid: AquaContourWatering.watering_active.encode(
                    0
                ),
                AquaContour.operation_mode.uuid: AquaContour.operation_mode.encode(0),
                AquaContourPosition.active_position.uuid: AquaContourPosition.active_position.encode(
                    0
                ),
            },
            id="aqua_contour",
        ),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_read_char_raw: dict[str, bytes],
    service_info: BluetoothServiceInfo,
    raw: dict[str, bytes],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup creates expected entities."""

    mock_read_char_raw.update(raw)

    mock_entry = await setup_entry(
        hass, platforms=[Platform.SELECT], service_info=service_info
    )
    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


async def test_state_change(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_read_char_raw: dict[str, bytes],
    scan_step: Callable[[], Awaitable[None]],
) -> None:
    """Test setup creates expected entities."""
    entity_id = "select.mock_title_watering"

    mock_read_char_raw[AquaContourWatering.watering_active.uuid] = (
        AquaContourWatering.watering_active.encode(AquaContourWateringMode.REST)
    )

    await setup_entry(
        hass, platforms=[Platform.SELECT], service_info=AQUA_CONTOUR_SERVICE_INFO
    )
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "rest"

    mock_read_char_raw[AquaContourWatering.watering_active.uuid] = (
        AquaContourWatering.watering_active.encode(AquaContourWateringMode.CONTOUR_1)
    )
    await scan_step()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "contour_1"


async def test_select(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    mock_read_char_raw: dict[str, bytes],
) -> None:
    """Test switching makes correct calls."""

    mock_read_char_raw[AquaContourWatering.watering_active.uuid] = b"\x00"
    entity_id = "select.mock_title_watering"
    await setup_entry(
        hass, platforms=[Platform.SELECT], service_info=AQUA_CONTOUR_SERVICE_INFO
    )
    assert hass.states.get(entity_id)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "rest"},
        blocking=True,
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "contour_3"},
        blocking=True,
    )

    assert mock_client.write_char.mock_calls == [
        call(AquaContourWatering.watering_active, 0),
        call(AquaContourWatering.watering_active, 3),
    ]
