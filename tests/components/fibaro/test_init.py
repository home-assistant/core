"""Test init methods."""

from unittest.mock import Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.fibaro.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import TEST_SERIALNUMBER, init_integration


async def test_migrate_device_identifiers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_fibaro_client: Mock,
) -> None:
    """Test migration converts integer Fibaro device identifiers to strings."""
    mock_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, 3)},  # type: ignore[arg-type]
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    migrated_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "3"), mock_config_entry.entry_id
    )
    assert migrated_device is not None
    assert migrated_device.identifiers == {(DOMAIN, "3")}
    assert mock_config_entry.version == 2


async def test_unload_integration(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_light: Mock,
    mock_room: Mock,
) -> None:
    """Test unload integration stops state listener."""
    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_light]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.LIGHT]):
        await init_integration(hass, mock_config_entry)
        # Act
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Assert
        assert mock_fibaro_client.unregister_update_handler.call_count == 1


async def test_load_integration_links_device_to_hub(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_light: Mock,
    mock_room: Mock,
) -> None:
    """Test load integration sets via_device_id for a light device to the hub device."""
    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_light]

    # Act
    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.LIGHT]):
        await init_integration(hass, mock_config_entry)

    # Assert
    hub_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_SERIALNUMBER), mock_config_entry.entry_id
    )
    light_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(mock_light.fibaro_id)), mock_config_entry.entry_id
    )
    assert hub_device is not None
    assert light_device is not None
    assert light_device.via_device_id == hub_device.id


async def test_child_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_thermostat_parent: Mock,
    mock_light: Mock,
    mock_zigbee_light: Mock,
    mock_power_sensor: Mock,
    mock_room: Mock,
) -> None:
    """Test child entities use child device info only on selected platforms."""
    mock_thermostat_parent.fibaro_id = 5
    main_device_with_endpoint = Mock()
    main_device_with_endpoint.fibaro_id = 15
    main_device_with_endpoint.parent_fibaro_id = 5
    main_device_with_endpoint.name = "Nested main"
    main_device_with_endpoint.properties = {"manufacturer": ""}
    main_device_with_endpoint.type = "com.fibaro.device"
    main_device_with_endpoint.base_type = "com.fibaro.device"
    main_device_with_endpoint.actions = {}
    main_device_with_endpoint.has_central_scene_event = False
    main_device_with_endpoint.value = Mock(has_value=False, is_bool_value=False)
    main_device_with_endpoint.has_endpoint_id = True
    main_device_with_endpoint.endpoint_id = 3
    mock_light.parent_fibaro_id = 5
    mock_light.endpoint_id = 1
    mock_light.has_endpoint_id = True
    mock_zigbee_light.name = "Test light 2"
    mock_zigbee_light.parent_fibaro_id = 5
    mock_zigbee_light.endpoint_id = 2
    mock_zigbee_light.has_endpoint_id = True
    mock_power_sensor.parent_fibaro_id = 5
    mock_power_sensor.endpoint_id = 2
    mock_power_sensor.has_endpoint_id = True
    mock_power_sensor.value.has_value = True
    mock_power_sensor.value.float_value.return_value = 6.6
    mock_power_sensor.unit = None
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [
        mock_thermostat_parent,
        main_device_with_endpoint,
        mock_light,
        mock_zigbee_light,
        mock_power_sensor,
    ]

    with (
        patch(
            "homeassistant.components.fibaro.PLATFORMS",
            [Platform.LIGHT, Platform.SENSOR],
        ),
        patch(
            "homeassistant.components.fibaro.find_master_devices",
            return_value=[mock_thermostat_parent, main_device_with_endpoint],
        ),
    ):
        await init_integration(hass, mock_config_entry)

    main_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "5"), mock_config_entry.entry_id
    )
    endpoint_device = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, "5_endpoint_1"), mock_config_entry.entry_id
    )
    second_endpoint_device = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, "5_endpoint_2"), mock_config_entry.entry_id
    )
    main_device_endpoint = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, "5_endpoint_3"), mock_config_entry.entry_id
    )
    light_entity = entity_registry.async_get(
        "light.test_climate_test_light_room_1_test_light"
    )
    second_light_entity = entity_registry.async_get(
        "light.test_climate_test_light_2_room_1_test_light_2"
    )
    additional_sensor_entity = entity_registry.async_get(
        "sensor.test_climate_test_light_2_room_1_test_sensor_power"
    )
    sensor_entity = entity_registry.async_get("sensor.test_climate_room_1_test_sensor")

    assert main_device is not None
    assert endpoint_device is not None
    assert endpoint_device.parent_device_id == main_device.id
    assert endpoint_device.name == mock_light.name
    assert second_endpoint_device is not None
    assert second_endpoint_device.parent_device_id == main_device.id
    assert second_endpoint_device.name == mock_zigbee_light.name
    assert main_device_endpoint is None
    assert light_entity is not None
    assert light_entity.device_id == endpoint_device.id
    assert second_light_entity is not None
    assert second_light_entity.device_id == second_endpoint_device.id
    assert additional_sensor_entity is not None
    assert additional_sensor_entity.device_id == second_endpoint_device.id
    assert sensor_entity is not None
    assert sensor_entity.device_id == main_device.id


async def test_single_endpoint_uses_main_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_thermostat_parent: Mock,
    mock_thermostat_with_operating_mode: Mock,
    mock_room: Mock,
) -> None:
    """Test a single endpoint remains attached to its main device."""
    mock_thermostat_parent.fibaro_id = 5

    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [
        mock_thermostat_parent,
        mock_thermostat_with_operating_mode,
    ]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.CLIMATE]):
        await init_integration(hass, mock_config_entry)

    main_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "5"), mock_config_entry.entry_id
    )
    child_device = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, "5_endpoint_1"), mock_config_entry.entry_id
    )
    child_entity = entity_registry.async_get("climate.test_climate_room_1_test_climate")

    assert main_device is not None
    assert child_device is None
    assert child_entity is not None
    assert child_entity.device_id == main_device.id


@pytest.mark.parametrize(
    ("fibaro_id", "removable"),
    [
        pytest.param(3, False, id="served_by_controller"),
        pytest.param(999, True, id="no_longer_served"),
    ],
)
async def test_remove_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_light: Mock,
    mock_room: Mock,
    fibaro_id: int,
    removable: bool,
) -> None:
    """Test only devices the controller no longer serves can be removed."""
    assert await async_setup_component(hass, "config", {})
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_light]
    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.LIGHT]):
        await init_integration(hass, mock_config_entry)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, str(fibaro_id))},
    )
    client = await hass_ws_client(hass)

    response = await client.remove_device(device.id)

    assert response["success"] is removable
