"""Test the Helty Flow Cloud binary sensor platform."""

from unittest.mock import AsyncMock, patch

from pyheltycloud import HeltyState, VmcMode
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import make_state

FILTER_ENTITY = "binary_sensor.vmc_soggiorno_filter"


@pytest.mark.usefixtures("mock_helty_cloud")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.helty_cloud.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("alarms", "expected"),
    [
        pytest.param("0000000000000020", STATE_ON, id="filter"),
        pytest.param("00000000000000A2", STATE_ON, id="filter_among_others"),
        pytest.param("0000000000000080", STATE_OFF, id="free_cooling_only"),
        pytest.param("0000000C00000000", STATE_OFF, id="undocumented_bits"),
    ],
)
async def test_filter_alarm(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
    alarms: str,
    expected: str,
) -> None:
    """Test only the filter bit of the alarm bitmap turns the sensor on."""
    mock_helty_cloud.get_last_telemetry.side_effect = lambda serial: make_state(
        alarms=alarms
    )
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FILTER_ENTITY).state == expected


async def test_no_alarm_bitmap(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a state without the alarm bitmap leaves the alarm unknown, not clear."""
    mock_helty_cloud.get_last_telemetry.side_effect = lambda serial: HeltyState(
        mode=VmcMode.SPEED_1
    )
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FILTER_ENTITY).state == STATE_UNKNOWN
