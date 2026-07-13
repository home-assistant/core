"""Tests for the WyBot sensor platform."""

from wybot.dp_models import Battery, DockInfo, SolarDockBattery, SolarEnergyHarvested

from homeassistant.components.wybot.sensor import (
    WyBotDataSourceSensor,
    WyBotDockTypeSensor,
    WyBotLastBLECommunicationSensor,
    WyBotLastMQTTCommunicationSensor,
    WyBotRobotBatterySensor,
    WyBotSolarDockBatterySensor,
    WyBotSolarEnergySensor,
    format_mac,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .wybot_platform_helpers import (
    add_entity,
    dp,
    make_coordinator,
    make_group,
    setup_integration,
)

IDX = "grp1"


def _robot_dps():
    """Robot dps."""
    return {"50": dp(Battery, id=50, type=0, len=2, data="0132")}


def _dock_dps():
    """Dock dps."""
    return {
        "221": dp(SolarDockBattery, id=221, type=0, len=3, data="01480a"),
        "131": dp(SolarEnergyHarvested, id=131, type=2, len=4, data="e8030000"),
        "214": dp(DockInfo, id=214, type=4, len=1, data="05"),
    }


def _coord(hass: HomeAssistant, **kwargs):
    """Coord."""
    group = make_group(device_dps=_robot_dps(), docker_dps=_dock_dps(), **kwargs)
    coord, entry = make_coordinator(hass, {IDX: group})
    return coord, entry, group


def test_format_mac() -> None:
    """Test format mac."""
    assert format_mac("CCBA97932A96") == "CC:BA:97:93:2A:96"
    assert format_mac("cc:ba:97:93:2a:96") == "CC:BA:97:93:2A:96"
    assert format_mac("cc-ba-97-93-2a-96") == "CC:BA:97:93:2A:96"


def _sensor_count(hass: HomeAssistant, entry) -> int:
    """Return the number of sensor entities registered for the entry."""
    ent_reg = er.async_get(hass)
    return sum(
        e.domain == "sensor"
        for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    )


async def test_async_setup_entry_adds_entities(hass: HomeAssistant) -> None:
    """Setting up a docked device registers the seven sensors."""
    group = make_group(device_dps=_robot_dps(), docker_dps=_dock_dps())
    entry = await setup_integration(hass, {IDX: group})
    assert _sensor_count(hass, entry) == 7


async def test_async_setup_entry_dockless_only_robot_battery(
    hass: HomeAssistant,
) -> None:
    """A group without a dock registers only the robot battery sensor."""
    group = make_group(device_dps=_robot_dps(), with_docker=False)
    entry = await setup_integration(hass, {IDX: group})
    assert _sensor_count(hass, entry) == 1


async def test_dock_sensor_unavailable_when_dock_removed(
    hass: HomeAssistant,
) -> None:
    """Dock sensors go unavailable if the group loses its dock."""
    coord, _, _ = _coord(hass)
    ent = WyBotSolarDockBatterySensor(idx=IDX, coordinator=coord)
    assert ent.available is True
    ent._data.docker = None
    assert ent.available is False


async def test_dock_added_after_setup_creates_dock_sensors(
    hass: HomeAssistant,
) -> None:
    """A dock appearing after setup adds the dock sensors without duplicates."""
    group = make_group(device_dps=_robot_dps(), with_docker=False)
    entry = await setup_integration(hass, {IDX: group})
    assert _sensor_count(hass, entry) == 1  # robot battery only

    # The group later gains a dock; the coordinator update runs the listener.
    docked = make_group(device_dps=_robot_dps(), docker_dps=_dock_dps())
    coord = entry.runtime_data
    coord.data = {IDX: docked}
    coord.async_set_updated_data(coord.data)
    await hass.async_block_till_done()

    assert _sensor_count(hass, entry) == 7


async def test_robot_battery_sensor(hass: HomeAssistant) -> None:
    """Test robot battery sensor."""
    coord, _, _ = _coord(hass)
    ent = WyBotRobotBatterySensor(idx=IDX, coordinator=coord)
    assert ent.native_value == 50
    assert ent.unique_id == "grp1_robot_battery"
    assert ent.translation_key == "robot_battery"
    assert ent.available is True
    info = ent.device_info
    assert info["identifiers"] == {("wybot", "grp1")}
    assert info["via_device"] == ("wybot", "grp1_dock")
    assert ("bluetooth", "CC:BA:97:93:2A:96") in info["connections"]


async def test_robot_battery_no_data(hass: HomeAssistant) -> None:
    """Test robot battery no data."""
    coord, _, _ = _coord(hass)
    ent = WyBotRobotBatterySensor(idx=IDX, coordinator=coord)
    ent._data = None
    assert ent.native_value is None
    assert ent.available is False


async def test_robot_battery_dp_missing(hass: HomeAssistant) -> None:
    """Test robot battery dp missing."""
    group = make_group(device_dps={}, docker_dps={})
    coord, _ = make_coordinator(hass, {IDX: group})
    ent = WyBotRobotBatterySensor(idx=IDX, coordinator=coord)
    assert ent.native_value is None


async def test_available_when_coordinator_unavailable(hass: HomeAssistant) -> None:
    """Test available when coordinator unavailable."""
    coord, _, _ = _coord(hass)
    ent = WyBotRobotBatterySensor(idx=IDX, coordinator=coord)
    coord._connection_available = False
    assert ent.available is False


async def test_available_when_idx_missing(hass: HomeAssistant) -> None:
    """Test available when idx missing."""
    coord, _, _ = _coord(hass)
    ent = WyBotRobotBatterySensor(idx=IDX, coordinator=coord)
    # Keep data truthy (coordinator.available) but drop this idx.
    coord.data = {"other": coord.data[IDX]}
    assert ent.available is False


async def test_solar_dock_battery_sensor(hass: HomeAssistant) -> None:
    """Test solar dock battery sensor."""
    coord, _, _ = _coord(hass)
    ent = WyBotSolarDockBatterySensor(idx=IDX, coordinator=coord)
    assert ent.native_value == 72
    assert ent.unique_id == "grp1_dock_battery"
    assert ent.translation_key == "dock_battery"
    info = ent.device_info
    assert info["identifiers"] == {("wybot", "grp1_dock")}
    assert info["name"] == "DS20 Solar Dock"
    assert info["model"] == "DS20"
    assert ("bluetooth", "3C:84:27:56:5A:1A") in info["connections"]


async def test_solar_dock_battery_no_data(hass: HomeAssistant) -> None:
    """Test solar dock battery no data."""
    coord, _, _ = _coord(hass)
    ent = WyBotSolarDockBatterySensor(idx=IDX, coordinator=coord)
    ent._data = None
    assert ent.native_value is None
    # device_info default (no data) branch.
    info = ent.device_info
    assert info["name"] == "Solar Dock"
    assert info["model"] == "Unknown"
    assert info["connections"] is None


async def test_solar_dock_battery_dp_missing(hass: HomeAssistant) -> None:
    """Test solar dock battery dp missing."""
    group = make_group(device_dps={}, docker_dps={})
    coord, _ = make_coordinator(hass, {IDX: group})
    ent = WyBotSolarDockBatterySensor(idx=IDX, coordinator=coord)
    assert ent.native_value is None


async def test_solar_energy_sensor(hass: HomeAssistant) -> None:
    """Test solar energy sensor."""
    coord, _, _ = _coord(hass)
    ent = WyBotSolarEnergySensor(idx=IDX, coordinator=coord)
    assert ent.native_value == 1000
    assert ent.unique_id == "grp1_solar_energy"
    assert ent.translation_key == "solar_energy"


async def test_solar_energy_no_data(hass: HomeAssistant) -> None:
    """Test solar energy no data."""
    coord, _, _ = _coord(hass)
    ent = WyBotSolarEnergySensor(idx=IDX, coordinator=coord)
    ent._data = None
    assert ent.native_value is None


async def test_solar_energy_dp_missing(hass: HomeAssistant) -> None:
    """Test solar energy dp missing."""
    group = make_group(device_dps={}, docker_dps={})
    coord, _ = make_coordinator(hass, {IDX: group})
    ent = WyBotSolarEnergySensor(idx=IDX, coordinator=coord)
    assert ent.native_value is None


async def test_dock_type_sensor_solar(hass: HomeAssistant) -> None:
    """Test dock type sensor solar."""
    coord, _, _ = _coord(hass)
    ent = WyBotDockTypeSensor(idx=IDX, coordinator=coord)
    assert ent.native_value == "Solar"
    assert ent.unique_id == "grp1_dock_type"
    assert ent.translation_key == "dock_type"
    attrs = ent.extra_state_attributes
    assert attrs["raw_value"] == "05"
    assert attrs["is_solar_dock"] is True


async def test_dock_type_sensor_standard(hass: HomeAssistant) -> None:
    """Test dock type sensor standard."""
    group = make_group(
        device_dps={},
        docker_dps={"214": dp(DockInfo, id=214, type=4, len=1, data="01")},
    )
    coord, _ = make_coordinator(hass, {IDX: group})
    ent = WyBotDockTypeSensor(idx=IDX, coordinator=coord)
    assert ent.native_value == "Standard"
    assert ent.extra_state_attributes["is_solar_dock"] is False


async def test_dock_type_no_data(hass: HomeAssistant) -> None:
    """Test dock type no data."""
    coord, _, _ = _coord(hass)
    ent = WyBotDockTypeSensor(idx=IDX, coordinator=coord)
    ent._data = None
    assert ent.native_value is None
    assert ent.extra_state_attributes == {}


async def test_dock_type_dp_missing(hass: HomeAssistant) -> None:
    """Test dock type dp missing."""
    group = make_group(device_dps={}, docker_dps={})
    coord, _ = make_coordinator(hass, {IDX: group})
    ent = WyBotDockTypeSensor(idx=IDX, coordinator=coord)
    assert ent.native_value is None
    assert ent.extra_state_attributes == {}


async def test_last_ble_communication_sensor(hass: HomeAssistant) -> None:
    """Test last ble communication sensor."""
    coord, _, _ = _coord(hass)
    now = dt_util.utcnow()
    coord._last_ble_poll["dock1"] = now
    coord._ble_available["dock1"] = True
    ent = WyBotLastBLECommunicationSensor(idx=IDX, coordinator=coord)
    assert ent.native_value == now
    assert ent.unique_id == "grp1_last_ble_communication"
    assert ent.translation_key == "last_ble_communication"
    attrs = ent.extra_state_attributes
    assert attrs["ble_available"] is True
    assert attrs["ble_name"] == "3C8427565A1A"


async def test_last_ble_communication_no_docker(hass: HomeAssistant) -> None:
    """Test last ble communication no docker."""
    group = make_group(device_dps=_robot_dps(), with_docker=False)
    coord, _ = make_coordinator(hass, {IDX: group})
    now = dt_util.utcnow()
    coord._last_ble_poll["dev1"] = now
    ent = WyBotLastBLECommunicationSensor(idx=IDX, coordinator=coord)
    assert ent.native_value == now
    # No docker -> extra attrs empty.
    assert ent.extra_state_attributes == {}


async def test_last_ble_communication_no_data(hass: HomeAssistant) -> None:
    """Test last ble communication no data."""
    coord, _, _ = _coord(hass)
    ent = WyBotLastBLECommunicationSensor(idx=IDX, coordinator=coord)
    ent._data = None
    assert ent.native_value is None
    assert ent.extra_state_attributes == {}


async def test_last_mqtt_communication_sensor(hass: HomeAssistant) -> None:
    """Test last mqtt communication sensor."""
    coord, _, _ = _coord(hass)
    now = dt_util.utcnow()
    coord._last_mqtt_data["dock1"] = now
    coord._mqtt_connected = True
    ent = WyBotLastMQTTCommunicationSensor(idx=IDX, coordinator=coord)
    assert ent.native_value == now
    assert ent.unique_id == "grp1_last_mqtt_communication"
    assert ent.translation_key == "last_mqtt_communication"
    assert ent.extra_state_attributes["mqtt_connected"] is True


async def test_last_mqtt_communication_no_docker(hass: HomeAssistant) -> None:
    """Test last mqtt communication no docker."""
    group = make_group(device_dps=_robot_dps(), with_docker=False)
    coord, _ = make_coordinator(hass, {IDX: group})
    now = dt_util.utcnow()
    coord._last_mqtt_data["dev1"] = now
    ent = WyBotLastMQTTCommunicationSensor(idx=IDX, coordinator=coord)
    assert ent.native_value == now
    assert ent.extra_state_attributes == {}


async def test_last_mqtt_communication_no_data(hass: HomeAssistant) -> None:
    """Test last mqtt communication no data."""
    coord, _, _ = _coord(hass)
    ent = WyBotLastMQTTCommunicationSensor(idx=IDX, coordinator=coord)
    ent._data = None
    assert ent.native_value is None


async def test_data_source_sensor_ble(hass: HomeAssistant) -> None:
    """Test data source sensor ble."""
    coord, _, _ = _coord(hass)
    coord._data_source["dock1"] = "ble"
    coord._ble_available["dock1"] = True
    coord._mqtt_connected = False
    now = dt_util.utcnow()
    coord._last_ble_poll["dock1"] = now
    coord._last_mqtt_data["dock1"] = now
    coord._mqtt_last_connected_at = now
    ent = WyBotDataSourceSensor(idx=IDX, coordinator=coord)
    assert ent.native_value == "bluetooth"
    assert ent.unique_id == "grp1_data_source"
    assert ent.translation_key == "data_source"
    attrs = ent.extra_state_attributes
    assert attrs["ble_available"] is True
    assert attrs["last_ble"] == now.isoformat()
    assert attrs["last_mqtt"] == now.isoformat()
    assert attrs["mqtt_last_connected_at"] == now.isoformat()


async def test_data_source_sensor_mqtt(hass: HomeAssistant) -> None:
    """Test data source sensor mqtt."""
    coord, _, _ = _coord(hass)
    coord._data_source["dock1"] = "mqtt"
    ent = WyBotDataSourceSensor(idx=IDX, coordinator=coord)
    assert ent.native_value == "cloud"


async def test_data_source_sensor_unknown(hass: HomeAssistant) -> None:
    """Test data source sensor unknown."""
    coord, _, _ = _coord(hass)
    ent = WyBotDataSourceSensor(idx=IDX, coordinator=coord)
    assert ent.native_value is None


async def test_data_source_sensor_no_docker_uses_device(hass: HomeAssistant) -> None:
    """Test data source sensor no docker uses device."""
    group = make_group(device_dps=_robot_dps(), with_docker=False)
    coord, _ = make_coordinator(hass, {IDX: group})
    coord._data_source["dev1"] = "ble"
    ent = WyBotDataSourceSensor(idx=IDX, coordinator=coord)
    assert ent.native_value == "bluetooth"
    # No docker -> extra attrs empty.
    assert ent.extra_state_attributes == {}


async def test_data_source_sensor_no_data(hass: HomeAssistant) -> None:
    """Test data source sensor no data."""
    coord, _, _ = _coord(hass)
    ent = WyBotDataSourceSensor(idx=IDX, coordinator=coord)
    ent._data = None
    assert ent.native_value is None
    assert ent.extra_state_attributes == {}


async def test_robot_name_fallbacks(hass: HomeAssistant) -> None:
    # name falsy -> device_name.
    """Test robot name fallbacks."""
    group = make_group(device_dps=_robot_dps(), name="")
    coord, _ = make_coordinator(hass, {IDX: group})
    ent = WyBotRobotBatterySensor(idx=IDX, coordinator=coord)
    assert ent.device_info["name"] == "Robot"

    # name and device_name falsy -> device_type.
    group.device.device_name = ""
    assert ent._get_robot_name() == "S2 Pro"

    # No data -> Unknown.
    ent._data = None
    assert ent._get_robot_name() == "Unknown"
    assert ent._get_robot_model() == "Unknown"


async def test_device_info_no_ble_no_docker(hass: HomeAssistant) -> None:
    """Test device info no ble no docker."""
    group = make_group(device_dps=_robot_dps(), with_docker=False)
    group.device.ble_name = ""
    coord, _ = make_coordinator(hass, {IDX: group})
    ent = WyBotRobotBatterySensor(idx=IDX, coordinator=coord)
    info = ent.device_info
    assert info["connections"] is None
    assert info["via_device"] is None


async def test_handle_coordinator_update(hass: HomeAssistant) -> None:
    """Test handle coordinator update."""
    coord, _, group = _coord(hass)
    ent = WyBotRobotBatterySensor(idx=IDX, coordinator=coord)
    await add_entity(hass, ent)
    # idx present -> refresh _data and write state.
    ent._handle_coordinator_update()
    assert ent._data is group
    state = hass.states.get(ent.entity_id)
    assert state is not None
    assert state.state == "50"


async def test_handle_coordinator_update_idx_missing(hass: HomeAssistant) -> None:
    """Test handle coordinator update idx missing."""
    coord, _, group = _coord(hass)
    ent = WyBotRobotBatterySensor(idx=IDX, coordinator=coord)
    await add_entity(hass, ent)
    coord.data = {}
    ent._handle_coordinator_update()
    # _data retained (idx not in coordinator.data).
    assert ent._data is group
