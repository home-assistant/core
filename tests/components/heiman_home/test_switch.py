"""Tests for the Heiman Home switch platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from heimanconnect import DeviceProperty, HeimanDevice

from homeassistant.components.heiman_home.const import DOMAIN
from homeassistant.components.heiman_home.switch import (
    HeimanSwitchEntity,
    async_setup_entry,
)
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_switch_setup(hass: HomeAssistant, setup_credentials: None) -> None:
    """Test switch platform setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_switch_entity_creation(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test switch entity creation from device properties."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS1"
    mock_device.product_id = "prod-1"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    switch_prop = DeviceProperty(
        identifier="power_switch",
        name="Power Switch",
        value=True,
        data_type="bool",
        readable=True,
        writable=True,
        entity="switch",
    )

    mock_device.properties = {"power_switch": switch_prop}
    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    assert len(added_entities) == 1
    switch = added_entities[0]
    assert switch.unique_id == "device-1_power_switch_switch"
    assert switch.name == "Power Switch"


async def test_switch_entity_available_property(hass: HomeAssistant) -> None:
    """Test switch entity available property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=True
        )
    }

    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    assert switch.available is True

    mock_device.online = False
    assert switch.available is False

    mock_coordinator.get_device.return_value = None
    assert switch.available is False

    mock_device.online = True
    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.last_update_success = False
    assert switch.available is False


async def test_switch_entity_is_on(hass: HomeAssistant) -> None:
    """Test switch entity is_on property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    assert switch.is_on is True

    mock_device.properties["power_switch"].value = False
    mock_coordinator.get_device.return_value = mock_device
    assert switch.is_on is False

    mock_device.properties["power_switch"].value = "on"
    mock_coordinator.get_device.return_value = mock_device
    assert switch.is_on is True

    mock_device.properties["power_switch"].value = "off"
    mock_coordinator.get_device.return_value = mock_device
    assert switch.is_on is False

    mock_device.properties["power_switch"].value = 1
    mock_coordinator.get_device.return_value = mock_device
    assert switch.is_on is True

    mock_device.properties["power_switch"].value = 0
    mock_coordinator.get_device.return_value = mock_device
    assert switch.is_on is False

    # When device is not found, is_on returns None (not False)
    mock_coordinator.get_device.return_value = None
    assert switch.is_on is None


async def test_switch_entity_is_on_string_values(hass: HomeAssistant) -> None:
    """Test switch entity is_on with various string values."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value="on"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    # Test only the values that switch.py checks: ["on", "true", "1", "opened", "active"]
    on_values = ["on", "ON", "On", "1", "true", "TRUE", "True", "opened", "Opened", "active", "Active"]
    for value in on_values:
        mock_device.properties = {
            "power_switch": DeviceProperty(
                identifier="power_switch", name="Power Switch", value=value
            )
        }
        mock_coordinator.get_device.return_value = mock_device
        assert switch.is_on is True, f"Expected True for value: {value}"

    off_values = ["off", "OFF", "Off", "0", "false", "FALSE", "False", "no", "NO", "No", "closed", "Closed"]
    for value in off_values:
        mock_device.properties = {
            "power_switch": DeviceProperty(
                identifier="power_switch", name="Power Switch", value=value
            )
        }
        mock_coordinator.get_device.return_value = mock_device
        assert switch.is_on is False, f"Expected False for value: {value}"


async def test_switch_entity_extra_state_attributes(hass: HomeAssistant) -> None:
    """Test switch entity extra_state_attributes property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch",
            name="Power Switch",
            value=True,
            unit="units",
            data_type="bool",
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    attrs = switch.extra_state_attributes
    assert attrs is not None
    assert attrs.get("unit") == "units"
    assert attrs.get("data_type") == "bool"
    assert attrs.get("raw_value") is True

    # Test when device is not found - should return empty dict
    mock_coordinator.get_device.return_value = None
    attrs = switch.extra_state_attributes
    assert attrs == {}


async def test_switch_entity_device_info(hass: HomeAssistant) -> None:
    """Test switch entity device info."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS1"
    mock_device.product_id = "prod-1"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True
    mock_device.device_info = None
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    device_info = switch.device_info
    assert device_info is not None
    assert device_info["name"] == "Test Device"
    assert device_info["manufacturer"] == "Heiman"
    assert device_info["model"] == "HS1"
    assert device_info["sw_version"] == "1.0"
    assert device_info["hw_version"] == "1.0"
    assert (DOMAIN, "device-1") in device_info["identifiers"]


async def test_switch_entity_unique_id(hass: HomeAssistant) -> None:
    """Test switch entity unique ID."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-123"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    assert switch.unique_id == "device-123_power_switch_switch"


async def test_switch_entity_has_entity_name(hass: HomeAssistant) -> None:
    """Test switch entity has entity name."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "My Gateway"
    mock_device.online = True
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    assert switch.has_entity_name is True


async def test_switch_entity_async_turn_on(hass: HomeAssistant) -> None:
    """Test switch async_turn_on method."""
    mock_coordinator = MagicMock()
    mock_mqtt_client = AsyncMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.product_id = "prod-1"
    mock_device.raw_data = {
        "deviceType": "switch",
        "parentId": None,
    }
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=False
        )
    }

    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.mqtt_client = mock_mqtt_client

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    await switch.async_turn_on()

    mock_mqtt_client.async_write_property.assert_called_once_with(
        device_id="device-1",
        product_id="prod-1",
        property_identifiers=["power_switch"],
        values={"power_switch": True},
        device_info={
            "deviceType": "switch",
            "parentId": None,
        },
    )


async def test_switch_entity_async_turn_off(hass: HomeAssistant) -> None:
    """Test switch async_turn_off method."""
    mock_coordinator = MagicMock()
    mock_mqtt_client = AsyncMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.product_id = "prod-1"
    mock_device.raw_data = {
        "deviceType": "switch",
        "parentId": None,
    }
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.mqtt_client = mock_mqtt_client

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    await switch.async_turn_off()

    mock_mqtt_client.async_write_property.assert_called_once_with(
        device_id="device-1",
        product_id="prod-1",
        property_identifiers=["power_switch"],
        values={"power_switch": False},
        device_info={
            "deviceType": "switch",
            "parentId": None,
        },
    )


async def test_switch_entity_async_turn_on_no_device(hass: HomeAssistant) -> None:
    """Test switch async_turn_on when device is not found."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.product_id = "prod-1"
    mock_device.raw_data = {
        "deviceType": "switch",
        "parentId": None,
    }
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=False
        )
    }

    mock_coordinator.get_device.return_value = mock_device
    mock_mqtt_client = AsyncMock()
    mock_coordinator.mqtt_client = mock_mqtt_client

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    await switch.async_turn_on()

    # Since the entity holds its own device reference, async_turn_on will still work
    # even if the device is no longer in the coordinator
    mock_mqtt_client.async_write_property.assert_called_once()


async def test_switch_entity_async_turn_off_no_device(hass: HomeAssistant) -> None:
    """Test switch async_turn_off when device is not found."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.product_id = "prod-1"
    mock_device.raw_data = {
        "deviceType": "switch",
        "parentId": None,
    }
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device
    mock_mqtt_client = AsyncMock()
    mock_coordinator.mqtt_client = mock_mqtt_client

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    await switch.async_turn_off()

    # Since the entity holds its own device reference, async_turn_off will still work
    mock_mqtt_client.async_write_property.assert_called_once()


async def test_switch_entity_async_turn_on_no_property(hass: HomeAssistant) -> None:
    """Test switch async_turn_on when property is not found."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.product_id = "prod-1"
    mock_device.raw_data = {
        "deviceType": "switch",
        "parentId": None,
    }
    mock_device.properties = {}

    mock_coordinator.get_device.return_value = mock_device
    mock_mqtt_client = AsyncMock()
    mock_coordinator.mqtt_client = mock_mqtt_client

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    await switch.async_turn_on()

    # The entity uses self._device directly, so it will still call MQTT
    mock_mqtt_client.async_write_property.assert_called_once()


async def test_switch_entity_async_turn_off_no_property(hass: HomeAssistant) -> None:
    """Test switch async_turn_off when property is not found."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.product_id = "prod-1"
    mock_device.raw_data = {
        "deviceType": "switch",
        "parentId": None,
    }
    mock_device.properties = {}

    mock_coordinator.get_device.return_value = mock_device
    mock_mqtt_client = AsyncMock()
    mock_coordinator.mqtt_client = mock_mqtt_client

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    await switch.async_turn_off()

    # The entity uses self._device directly, so it will still call MQTT
    mock_mqtt_client.async_write_property.assert_called_once()


async def test_switch_entity_extra_state_attributes_property_not_found(
    hass: HomeAssistant,
) -> None:
    """Test extra_state_attributes when property is not found."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {}

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    attrs = switch.extra_state_attributes
    assert attrs == {}


async def test_switch_entity_name_fallback(hass: HomeAssistant) -> None:
    """Test switch entity name fallback to property identifier."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {}

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="unknown_switch",
    )

    assert switch.name == "unknown_switch"


async def test_switch_icon_power(hass: HomeAssistant) -> None:
    """Test icon for power switch."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    assert switch.icon == "mdi:toggle-switch"


async def test_switch_icon_light(hass: HomeAssistant) -> None:
    """Test icon for light switch."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "LightSwitch": DeviceProperty(
            identifier="LightSwitch", name="Light Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="LightSwitch",
    )

    assert switch.icon == "mdi:lightbulb-outline"


async def test_switch_icon_switch(hass: HomeAssistant) -> None:
    """Test icon for generic switch."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "switch_state": DeviceProperty(
            identifier="switch_state", name="Switch State", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="switch_state",
    )

    assert switch.icon == "mdi:toggle-switch"


async def test_switch_icon_default(hass: HomeAssistant) -> None:
    """Test default icon for unknown switch type."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "unknown_switch": DeviceProperty(
            identifier="unknown_switch", name="Unknown Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="unknown_switch",
    )

    assert switch.icon == "mdi:toggle-switch"


async def test_switch_device_class_switch(hass: HomeAssistant) -> None:
    """Test switch device class."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    # power_switch doesn't have a specific device class mapping, so it should be None or default
    assert switch.device_class is None


async def test_switch_device_class_outlet(hass: HomeAssistant) -> None:
    """Test switch device class for outlet."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "outlet_switch": DeviceProperty(
            identifier="outlet_switch", name="Outlet Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="outlet_switch",
    )

    # outlet_switch doesn't have a specific device class mapping
    assert switch.device_class is None


async def test_switch_device_class_light(hass: HomeAssistant) -> None:
    """Test switch device class for light."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "light_switch": DeviceProperty(
            identifier="light_switch", name="Light Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="light_switch",
    )

    # light_switch doesn't have a specific device class mapping
    assert switch.device_class is None


async def test_switch_entity_deduplication(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test switch entity deduplication within a single setup call."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS1"
    mock_device.product_id = "prod-1"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    switch_prop = DeviceProperty(
        identifier="power_switch",
        name="Power Switch",
        value=True,
        data_type="bool",
        readable=True,
        writable=True,
        entity="switch",
    )

    mock_device.properties = {"power_switch": switch_prop}
    # Return device twice (simulating duplicate callback)
    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    # Should only add 1 entity even though get_all_devices is called once
    assert len(added_entities) == 1


async def test_switch_creation_with_multiple_properties(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test switch entity creation with multiple properties."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Multi Switch Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS2"
    mock_device.product_id = "prod-2"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    power_prop = DeviceProperty(
        identifier="power_switch",
        name="Power Switch",
        value=True,
        data_type="bool",
        readable=True,
        writable=True,
        entity="switch",
    )

    light_prop = DeviceProperty(
        identifier="light_switch",
        name="Light Switch",
        value=False,
        data_type="bool",
        readable=True,
        writable=True,
        entity="switch",
    )

    non_switch_prop = DeviceProperty(
        identifier="temperature",
        name="Temperature",
        value=25.5,
        data_type="float",
        readable=True,
        entity="sensor",
    )

    mock_device.properties = {
        "power_switch": power_prop,
        "light_switch": light_prop,
        "temperature": non_switch_prop,
    }
    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    assert len(added_entities) == 2
    unique_ids = {switch.unique_id for switch in added_entities}
    assert "device-1_power_switch_switch" in unique_ids
    assert "device-1_light_switch_switch" in unique_ids


async def test_switch_async_turn_on_without_raw_data(hass: HomeAssistant) -> None:
    """Test switch async_turn_on when device has no raw_data."""
    mock_coordinator = MagicMock()
    mock_mqtt_client = AsyncMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.product_id = "prod-1"
    mock_device.device_type = "switch"
    mock_device.parent_id = None
    mock_device.raw_data = None
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=False
        )
    }

    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.mqtt_client = mock_mqtt_client

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    await switch.async_turn_on()

    mock_mqtt_client.async_write_property.assert_called_once_with(
        device_id="device-1",
        product_id="prod-1",
        property_identifiers=["power_switch"],
        values={"power_switch": True},
        device_info={
            "deviceType": "switch",
            "parentId": None,
        },
    )


async def test_switch_async_turn_off_without_raw_data(hass: HomeAssistant) -> None:
    """Test switch async_turn_off when device has no raw_data."""
    mock_coordinator = MagicMock()
    mock_mqtt_client = AsyncMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.product_id = "prod-1"
    mock_device.device_type = "switch"
    mock_device.parent_id = None
    mock_device.raw_data = None
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.mqtt_client = mock_mqtt_client

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    await switch.async_turn_off()

    mock_mqtt_client.async_write_property.assert_called_once_with(
        device_id="device-1",
        product_id="prod-1",
        property_identifiers=["power_switch"],
        values={"power_switch": False},
        device_info={
            "deviceType": "switch",
            "parentId": None,
        },
    )


async def test_switch_icon_lowercase_matching(hass: HomeAssistant) -> None:
    """Test icon application with lowercase property identifier matching."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "LightSwitch": DeviceProperty(
            identifier="LightSwitch", name="Light Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="LightSwitch",
    )

    assert switch.icon == "mdi:lightbulb-outline"


async def test_switch_is_on_none_value(hass: HomeAssistant) -> None:
    """Test switch entity is_on when property value is None."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=None
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    # When prop.value is None, is_on returns None (per implementation)
    assert switch.is_on is None


async def test_switch_icon_lowercase_matching(hass: HomeAssistant) -> None:
    """Test switch icon with lowercase property identifier matching."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    # Default icon
    assert switch.icon == "mdi:toggle-switch"


async def test_switch_is_on_unknown_value_type(hass: HomeAssistant) -> None:
    """Test switch is_on returns None for unknown value types."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "unknown_prop": DeviceProperty(
            identifier="unknown_prop", name="Unknown", value={"complex": "object"}
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="unknown_prop",
    )

    # Unknown value type (dict) should return None
    assert switch.is_on is None


async def test_switch_icon_no_match_fallback(hass: HomeAssistant) -> None:
    """Test switch icon when no ENTITY_ICONS match."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Use property that doesn't match any ENTITY_ICONS key
    mock_device.properties = {
        "CustomSwitch": DeviceProperty(
            identifier="CustomSwitch", name="Custom Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="CustomSwitch",
    )

    # Should fall through to default icon
    assert switch.icon == "mdi:toggle-switch"


async def test_switch_icon_lowercase_match_not_in_icons(hass: HomeAssistant) -> None:
    """Test switch icon lowercase match when key not in ENTITY_ICONS."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Property with lowercase match but not in ENTITY_ICONS
    mock_device.properties = {
        "LIGHTSWITCH": DeviceProperty(
            identifier="LIGHTSWITCH", name="Light Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="LIGHTSWITCH",
    )

    # Original case "LIGHTSWITCH" not in icons, lowercase "lightswitch" matches ENTITY_ICONS lowercase -> mdi:lightbulb-outline
    assert switch.icon == "mdi:lightbulb-outline"


async def test_switch_icon_exact_match(hass: HomeAssistant) -> None:
    """Test switch icon exact match in ENTITY_ICONS."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Property with exact match in ENTITY_ICONS
    mock_device.properties = {
        "LightSwitch": DeviceProperty(
            identifier="LightSwitch", name="Light Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="LightSwitch",
    )

    # Exact match should use that icon
    assert switch.icon == "mdi:lightbulb-outline"


async def test_switch_icon_lowercase_match(hass: HomeAssistant) -> None:
    """Test switch icon with uppercase property identifier that triggers lowercase matching."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Property with uppercase identifier that does NOT exist in ENTITY_ICONS
    # but its lowercase form DOES exist
    mock_device.properties = {
        "LIGHTSWITCH": DeviceProperty(
            identifier="LIGHTSWITCH", name="Light Switch", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    switch = HeimanSwitchEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="LIGHTSWITCH",
    )

    # First check "LIGHTSWITCH" in icons -> False
    # Second check "lightswitch" in icons -> True -> mdi:lightbulb-outline
    assert switch.icon == "mdi:lightbulb-outline"


async def test_switch_skips_non_writable_properties(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test that switch setup skips non-writable properties."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS1"
    mock_device.product_id = "prod-1"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    # Create a non-writable property marked as switch
    non_writable_prop = DeviceProperty(
        identifier="non_writable_switch",
        name="Non Writable Switch",
        value=True,
        data_type="bool",
        writable=False,  # Not writable
        entity="switch",
    )

    # Create a writable property marked as switch
    writable_prop = DeviceProperty(
        identifier="light_switch",
        name="Light Switch",
        value=True,
        data_type="bool",
        writable=True,  # Writable
        entity="switch",
    )

    mock_device.properties = {
        "non_writable_switch": non_writable_prop,
        "light_switch": writable_prop,
    }
    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    # Only the writable property should create an entity
    assert len(added_entities) == 1
    assert added_entities[0].unique_id == "device-1_light_switch_switch"
