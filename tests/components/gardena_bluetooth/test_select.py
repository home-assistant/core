"""Test Gardena Bluetooth sensor."""

from collections.abc import Awaitable, Callable
from unittest.mock import Mock, call

from gardena_bluetooth.const import AquaContourWatering
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant

from . import AQUA_CONTOUR_SERVICE_INFO, setup_entry

from tests.common import MockConfigEntry


@pytest.fixture
def mock_chars(mock_read_char_raw):
    """Mock data on device."""
    mock_read_char_raw[AquaContourWatering.watering_active.uuid] = b"\x00"
    return mock_read_char_raw


async def test_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_client: Mock,
    mock_chars: dict[str, bytes],
    scan_step: Callable[[], Awaitable[None]],
) -> None:
    """Test setup creates expected entities."""

    entity_id = "select.aqua_contour_watering"
    await setup_entry(
        hass, platforms=[Platform.SELECT], service_info=AQUA_CONTOUR_SERVICE_INFO
    )
    assert hass.states.get(entity_id) == snapshot

    mock_chars[AquaContourWatering.watering_active.uuid] = b"\x01"
    await scan_step()
    assert hass.states.get(entity_id) == snapshot


async def test_select(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    mock_chars: dict[str, bytes],
) -> None:
    """Test switching makes correct calls."""

    entity_id = "select.aqua_contour_watering"
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
