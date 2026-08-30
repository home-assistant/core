"""Tests for the Watergate number platform."""

from collections.abc import Generator
from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from watergate_local_api import WatergateApiException
from watergate_local_api.models import AutoShutOffState

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import (
    AsyncMock,
    MockConfigEntry,
    async_fire_time_changed,
    patch,
    snapshot_platform,
)

VOLUME_ENTITY_ID = "number.sonic_auto_shut_off_volume_threshold"
DURATION_ENTITY_ID = "number.sonic_auto_shut_off_duration_threshold"


@pytest.mark.usefixtures("mock_watergate_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_entry: MockConfigEntry,
) -> None:
    """Snapshot the number entities and their registry entries."""
    with patch("homeassistant.components.watergate.PLATFORMS", [Platform.NUMBER]):
        await init_integration(hass, mock_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "expected_kwargs"),
    [
        pytest.param(VOLUME_ENTITY_ID, {"volume": 250}, id="volume"),
        pytest.param(DURATION_ENTITY_ID, {"duration": 250}, id="duration"),
    ],
)
async def test_setting_threshold_calls_client(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
    entity_id: str,
    expected_kwargs: dict[str, int],
) -> None:
    """Setting a threshold calls the client with the requested value."""
    await init_integration(hass, mock_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 250},
        blocking=True,
    )

    update_mock = mock_watergate_client.async_update_auto_shut_off
    update_mock.assert_called_once_with(**expected_kwargs)
    # Home Assistant coerces the service value to a float, the device expects an integer.
    assert all(
        isinstance(value, int) for value in update_mock.call_args.kwargs.values()
    )


async def test_setting_fractional_threshold_rounds_to_integer(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
) -> None:
    """A fractional threshold is rounded, the device only accepts whole liters."""
    await init_integration(hass, mock_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: VOLUME_ENTITY_ID, ATTR_VALUE: 250.6},
        blocking=True,
    )

    mock_watergate_client.async_update_auto_shut_off.assert_called_once_with(volume=251)


@pytest.mark.parametrize(
    ("entity_id", "initial_state", "polled_state"),
    [
        pytest.param(VOLUME_ENTITY_ID, "1000", "500", id="volume"),
        pytest.param(DURATION_ENTITY_ID, "60", "15", id="duration"),
    ],
)
async def test_number_reflects_polled_state(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
    initial_state: str,
    polled_state: str,
) -> None:
    """The thresholds reflect an auto-shut-off change picked up by polling."""
    await init_integration(hass, mock_entry)

    assert hass.states.get(entity_id).state == initial_state

    mock_watergate_client.async_get_auto_shut_off.return_value = AutoShutOffState(
        True, 500, 15
    )
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == polled_state


@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param(VOLUME_ENTITY_ID, id="volume"),
        pytest.param(DURATION_ENTITY_ID, id="duration"),
    ],
)
async def test_number_raises_on_client_failure(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
    entity_id: str,
) -> None:
    """Client failure while setting a threshold surfaces as a HomeAssistantError."""
    await init_integration(hass, mock_entry)

    mock_watergate_client.async_update_auto_shut_off.side_effect = (
        WatergateApiException("boom")
    )

    with pytest.raises(HomeAssistantError, match="Failed to update auto shut-off"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 250},
            blocking=True,
        )
