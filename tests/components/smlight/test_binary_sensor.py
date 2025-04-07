"""Tests for the SMLIGHT binary sensor platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pysmlight.const import Events
from pysmlight.sse import MessageEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smlight.const import SCAN_INTERNET_INTERVAL
from homeassistant.const import STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_mock_event_function
from .conftest import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = [
    pytest.mark.usefixtures(
        "mock_smlight_client",
    )
]

MOCK_INET_STATE = MessageEvent(
    type="EVENT_INET_STATE",
    message="EVENT_INET_STATE",
    data="ok",
    origin="http://slzb-06.local",
    last_event_id="",
)


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.BINARY_SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the SMLIGHT binary sensors."""
    entry = await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)

    await hass.config_entries.async_unload(entry.entry_id)


async def test_disabled_by_default_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test wifi sensor is disabled by default ."""
    await setup_integration(hass, mock_config_entry)

    for sensor in ("wi_fi", "vpn"):
        assert not hass.states.get(f"binary_sensor.mock_title_{sensor}")

        assert (
            entry := entity_registry.async_get(f"binary_sensor.mock_title_{sensor}")
        )
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_internet_sensor_event(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test internet sensor event."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.mock_title_internet")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    assert len(mock_smlight_client.get_param.mock_calls) == 1
    mock_smlight_client.get_param.assert_called_with("inetState")

    freezer.tick(SCAN_INTERNET_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(mock_smlight_client.get_param.mock_calls) == 2
    mock_smlight_client.get_param.assert_called_with("inetState")

    event_function = get_mock_event_function(
        mock_smlight_client, Events.EVENT_INET_STATE
    )

    event_function(MOCK_INET_STATE)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.mock_title_internet")
    assert state is not None
    assert state.state == STATE_ON
