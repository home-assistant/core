"""Tests for the Bosch SHC cover platform."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from boschshcpy import SHCShutterControl
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
    STATE_OPEN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import cover_device, setup_integration

from tests.common import MockConfigEntry, snapshot_platform

OPENING = SHCShutterControl.ShutterControlService.State.OPENING
CLOSING = SHCShutterControl.ShutterControlService.State.CLOSING

COVER_ENTITY_ID = "cover.cover"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the cover platform."""
    with patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.COVER]):
        yield


@pytest.mark.parametrize(
    "device_buckets",
    [
        pytest.param(
            {
                "shutter_controls": [
                    cover_device(),
                    cover_device(device_id="hdm:HomeMaticIP:cover2", level=1.0),
                ]
            },
            id="entities",
        )
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot the cover entities two shutter_controls devices create."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_session")
async def test_setup_no_devices_adds_nothing(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """No shutter_controls devices means no cover entities are created."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.async_all(COVER_DOMAIN) == []


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_controls": [cover_device(level=1.0)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_current_cover_position_open(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A fully-open shutter (level=1.0) reports state open and position 100."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(COVER_ENTITY_ID)
    assert state.state == STATE_OPEN
    assert state.attributes["current_position"] == 100


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_controls": [cover_device(level=0.0)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_current_cover_position_closed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A fully-closed shutter (level=0.0) reports state closed and position 0."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(COVER_ENTITY_ID)
    assert state.state == STATE_CLOSED
    assert state.attributes["current_position"] == 0


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_controls": [cover_device(level=0.1)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_current_cover_position_partially_open(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A partially-open shutter is reported as open, not closed."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(COVER_ENTITY_ID)
    assert state.state == STATE_OPEN
    assert state.attributes["current_position"] == 10


@pytest.mark.parametrize(
    ("device_buckets", "expected_cover_state"),
    [
        pytest.param(
            {"shutter_controls": [cover_device(level=0.5, operation_state=OPENING)]},
            CoverState.OPENING,
            id="opening",
        ),
        pytest.param(
            {"shutter_controls": [cover_device(level=0.5, operation_state=CLOSING)]},
            CoverState.CLOSING,
            id="closing",
        ),
    ],
    indirect=["device_buckets"],
)
@pytest.mark.usefixtures("mock_session")
async def test_is_opening_and_is_closing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    expected_cover_state: CoverState,
) -> None:
    """The entity state reflects the device's ShutterControlService.State."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(COVER_ENTITY_ID)
    assert state.state == expected_cover_state


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_controls": [cover_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_stop_cover_calls_device_stop(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """The stop_cover service delegates to the device's stop()."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.shutter_controls[0]

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )

    device.stop.assert_called_once_with()


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_controls": [cover_device(level=0.0)]}],
    indirect=True,
)
async def test_open_cover_sets_level_to_full(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """The open_cover service writes level=1.0 (fully open)."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.shutter_controls[0]

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )

    assert device.level == 1.0


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_controls": [cover_device(level=1.0)]}],
    indirect=True,
)
async def test_close_cover_sets_level_to_zero(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """The close_cover service writes level=0.0 (fully closed)."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.shutter_controls[0]

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )

    assert device.level == 0.0


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_controls": [cover_device()]}],
    indirect=True,
)
@pytest.mark.parametrize(
    ("position", "expected_level"),
    [
        pytest.param(0, 0.0, id="closed"),
        pytest.param(50, 0.5, id="half_open"),
        pytest.param(100, 1.0, id="fully_open"),
        pytest.param(42, 0.42, id="arbitrary"),
    ],
)
async def test_set_cover_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    position: int,
    expected_level: float,
) -> None:
    """The set_cover_position service converts 0..100 position back to a 0..1 level."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.shutter_controls[0]

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID, ATTR_POSITION: position},
        blocking=True,
    )

    assert device.level == pytest.approx(expected_level)
