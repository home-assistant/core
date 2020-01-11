"""Common tests for HomematicIP devices."""
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import get_mock_hap
from .helper import async_manipulate_test_data, get_and_check_entity_basics


async def test_hmip_remove_device(hass, default_mock_hap):
    """Test Remove of hmip device."""
    entity_id = "light.treppe"
    entity_name = "Treppe"
    device_model = "HmIP-BSL"

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, default_mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert hmip_device

    device_registry = await dr.async_get_registry(hass)
    entity_registry = await er.async_get_registry(hass)

    pre_device_count = len(device_registry.devices)
    pre_entity_count = len(entity_registry.entities)
    pre_mapping_count = len(default_mock_hap.hmip_device_by_entity_id)

    hmip_device.fire_remove_event()

    await hass.async_block_till_done()

    assert len(device_registry.devices) == pre_device_count - 1
    assert len(entity_registry.entities) == pre_entity_count - 3
    assert len(default_mock_hap.hmip_device_by_entity_id) == pre_mapping_count - 3


async def test_hmip_remove_group(hass, default_mock_hap):
    """Test Remove of hmip group."""
    entity_id = "switch.strom_group"
    entity_name = "Strom Group"
    device_model = None

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, default_mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert hmip_device

    device_registry = await dr.async_get_registry(hass)
    entity_registry = await er.async_get_registry(hass)

    pre_device_count = len(device_registry.devices)
    pre_entity_count = len(entity_registry.entities)
    pre_mapping_count = len(default_mock_hap.hmip_device_by_entity_id)

    hmip_device.fire_remove_event()

    await hass.async_block_till_done()

    assert len(device_registry.devices) == pre_device_count
    assert len(entity_registry.entities) == pre_entity_count - 1
    assert len(default_mock_hap.hmip_device_by_entity_id) == pre_mapping_count - 1


async def test_all_devices_unavailable_when_hap_not_connected(hass, default_mock_hap):
    """Test make all devices unavaulable when hap is not connected."""
    entity_id = "light.treppe"
    entity_name = "Treppe"
    device_model = "HmIP-BSL"

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, default_mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert hmip_device

    assert default_mock_hap.home.connected

    await async_manipulate_test_data(hass, default_mock_hap.home, "connected", False)

    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_UNAVAILABLE


async def test_hap_reconnected(hass, default_mock_hap):
    """Test reconnect hap."""
    entity_id = "light.treppe"
    entity_name = "Treppe"
    device_model = "HmIP-BSL"

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, default_mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert hmip_device

    assert default_mock_hap.home.connected

    await async_manipulate_test_data(hass, default_mock_hap.home, "connected", False)

    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_UNAVAILABLE

    default_mock_hap._accesspoint_connected = False  # pylint: disable=protected-access
    await async_manipulate_test_data(hass, default_mock_hap.home, "connected", True)
    await hass.async_block_till_done()
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON


async def test_hap_with_name(hass, mock_connection, hmip_config_entry):
    """Test hap with name."""
    home_name = "TestName"
    entity_id = f"light.{home_name.lower()}_treppe"
    entity_name = f"{home_name} Treppe"
    device_model = "HmIP-BSL"

    hmip_config_entry.data["name"] = home_name
    mock_hap = await get_mock_hap(hass, mock_connection, hmip_config_entry)
    assert mock_hap

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert hmip_device
    assert ha_state.state == STATE_ON
    assert ha_state.attributes["friendly_name"] == entity_name


async def test_hmip_reset_energy_counter_services(hass, mock_hap_with_service):
    """Test reset_energy_counter service."""
    entity_id = "switch.pc"
    entity_name = "Pc"
    device_model = "HMIP-PSM"

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap_with_service, entity_id, entity_name, device_model
    )
    assert ha_state

    await hass.services.async_call(
        "homematicip_cloud",
        "reset_energy_counter",
        {"entity_id": "switch.pc"},
        blocking=True,
    )
    assert hmip_device.mock_calls[-1][0] == "reset_energy_counter"
    assert len(hmip_device._connection.mock_calls) == 2  # pylint: disable=W0212

    await hass.services.async_call(
        "homematicip_cloud", "reset_energy_counter", {"entity_id": "all"}, blocking=True
    )
    assert hmip_device.mock_calls[-1][0] == "reset_energy_counter"
    assert len(hmip_device._connection.mock_calls) == 12  # pylint: disable=W0212
