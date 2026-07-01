"""Test OpenAQ sensors."""

from unittest.mock import MagicMock

from openaq import NotAuthorizedError, TimeoutError as OpenAQTimeoutError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import const as ha_const
from homeassistant.components.openaq.const import DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.translation import async_get_translations

from . import setup_integration
from .conftest import LOCATION_ID, make_latest, make_response, make_sensor

from tests.common import MockConfigEntry, snapshot_platform


async def async_load_entity_translations(hass: HomeAssistant) -> None:
    """Load OpenAQ entity translations."""
    await async_get_translations(hass, "en", "entity", [DOMAIN])


@pytest.mark.usefixtures("mock_openaq_client")
async def test_sensor_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test OpenAQ sensor snapshots."""
    await async_load_entity_translations(hass)
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_openaq_client")
async def test_sensor_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test OpenAQ sensor entities."""
    await async_load_entity_translations(hass)
    await setup_integration(hass, mock_config_entry)

    pm25 = entity_registry.async_get("sensor.del_norte_pm2_5")
    assert pm25 is not None
    assert pm25.unique_id == f"{LOCATION_ID}_pm25"
    assert pm25.capabilities == {ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT}
    assert pm25.options == {"sensor": {"suggested_display_precision": 1}}
    assert (state := hass.states.get("sensor.del_norte_pm2_5")) is not None
    assert state.state == "12.1"
    assert state.attributes["device_class"] == SensorDeviceClass.PM25
    assert (
        state.attributes["unit_of_measurement"]
        == ha_const.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    co = entity_registry.async_get("sensor.del_norte_carbon_monoxide")
    assert co is not None
    assert co.capabilities == {ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT}
    assert co.options == {"sensor": {"suggested_display_precision": 2}}
    assert (state := hass.states.get("sensor.del_norte_carbon_monoxide")) is not None
    assert state.attributes["device_class"] == SensorDeviceClass.CO
    assert state.attributes["unit_of_measurement"] == "ppm"

    no2 = entity_registry.async_get("sensor.del_norte_nitrogen_dioxide")
    assert no2 is not None
    assert no2.capabilities == {ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT}
    assert no2.options == {"sensor": {"suggested_display_precision": 1}}
    assert (state := hass.states.get("sensor.del_norte_nitrogen_dioxide")) is not None
    assert state.attributes["unit_of_measurement"] == "ppb"

    assert entity_registry.async_get("sensor.del_norte_unsupported") is None

    device = device_registry.async_get_device(
        identifiers={("openaq", str(LOCATION_ID))}
    )
    assert device is not None
    assert device.name == "Del Norte"


async def test_missing_latest_values_create_unknown_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_openaq_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors without latest values are created with unknown state."""
    mock_openaq_client.locations.latest.return_value = make_response(
        [make_latest(1, 8.5), make_latest(2, None)]
    )
    mock_openaq_client.locations.sensors.return_value = make_response(
        [make_sensor(1, "pm1"), make_sensor(2, "pm25")]
    )

    await setup_integration(hass, mock_config_entry)

    assert entity_registry.async_get("sensor.del_norte_pm1") is not None
    assert entity_registry.async_get("sensor.del_norte_pm2_5") is not None
    assert (state := hass.states.get("sensor.del_norte_pm2_5")) is not None
    assert state.state == STATE_UNKNOWN


async def test_entity_unavailable_on_update_failure(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors become unavailable when refresh fails."""
    await setup_integration(hass, mock_config_entry)
    coordinator = next(iter(mock_config_entry.runtime_data.coordinators.values()))
    mock_openaq_client.locations.latest.side_effect = OpenAQTimeoutError("Timeout")

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.del_norte_pm2_5")) is not None
    assert state.state == STATE_UNAVAILABLE


async def test_entity_unavailable_on_auth_failure(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors become unavailable when runtime authentication fails."""
    await setup_integration(hass, mock_config_entry)
    coordinator = next(iter(mock_config_entry.runtime_data.coordinators.values()))
    mock_openaq_client.locations.latest.side_effect = NotAuthorizedError(
        "Invalid API key"
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert any(
        flow["handler"] == DOMAIN and flow["context"]["source"] == "reauth"
        for flow in hass.config_entries.flow.async_progress()
    )
    assert (state := hass.states.get("sensor.del_norte_pm2_5")) is not None
    assert state.state == STATE_UNAVAILABLE


async def test_entity_unknown_when_measurement_disappears(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors handle measurements disappearing after setup."""
    await setup_integration(hass, mock_config_entry)
    coordinator = next(iter(mock_config_entry.runtime_data.coordinators.values()))
    mock_openaq_client.locations.latest.return_value = make_response(
        [make_latest(1, 8.5)]
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.del_norte_pm2_5")) is not None
    assert state.state == STATE_UNKNOWN
