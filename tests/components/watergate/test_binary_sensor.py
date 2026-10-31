"""Tests for the Watergate binary sensor platform."""

from collections.abc import Generator
import copy
from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    AsyncMock,
    MockConfigEntry,
    async_fire_time_changed,
    patch,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion
from watergate_local_api import WatergateApiException

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration
from .const import DEFAULT_DEVICE_STATE_V2, DEFAULT_NETWORKING_STATE

WATER_FLOWING = "binary_sensor.sonic_water_flowing"
MQTT_CONNECTED = "binary_sensor.sonic_mqtt_connected"
WIFI_CONNECTED = "binary_sensor.sonic_wi_fi_connected"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
    snapshot: SnapshotAssertion,
) -> None:
    """Test states of the binary sensors."""
    with patch(
        "homeassistant.components.watergate.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await init_integration(hass, mock_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


async def test_enabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test only water flowing is enabled by default; connectivity ones are disabled diagnostics."""
    with patch(
        "homeassistant.components.watergate.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await init_integration(hass, mock_entry)

    assert hass.states.get(WATER_FLOWING) is not None
    for entity_id in (MQTT_CONNECTED, WIFI_CONNECTED):
        entry = entity_registry.async_get(entity_id)
        assert entry
        assert entry.disabled
        assert entry.entity_category is EntityCategory.DIAGNOSTIC
        assert entry.original_device_class is BinarySensorDeviceClass.CONNECTIVITY


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_states_are_off_when_the_device_reports_false(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test the binary sensors are off when the device reports boolean false."""
    state = copy.copy(DEFAULT_DEVICE_STATE_V2)
    state.water_flow_indicator = False
    networking = copy.copy(DEFAULT_NETWORKING_STATE)
    networking.mqtt_connected = False
    networking.wifi_connected = False
    mock_watergate_client.async_get_device_state_v2.return_value = state
    mock_watergate_client.async_get_networking.return_value = networking

    with patch(
        "homeassistant.components.watergate.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await init_integration(hass, mock_entry)

    assert hass.states.get(WATER_FLOWING).state == STATE_OFF
    assert hass.states.get(MQTT_CONNECTED).state == STATE_OFF
    assert hass.states.get(WIFI_CONNECTED).state == STATE_OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_unavailable_when_source_data_is_missing(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the binary sensors become unavailable when the device reports no state."""
    mock_watergate_client.async_get_device_state_v2.side_effect = WatergateApiException(
        "Unsupported media type"
    )
    with patch(
        "homeassistant.components.watergate.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await init_integration(hass, mock_entry)

    assert hass.states.get(WATER_FLOWING).state == STATE_ON

    mock_watergate_client.async_get_device_state.return_value = None
    freezer.tick(timedelta(minutes=2, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(WATER_FLOWING).state == STATE_UNAVAILABLE
