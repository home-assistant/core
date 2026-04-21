"""Tests for the Heiman Home button platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from heimanconnect import DeviceProperty, HeimanDevice

from homeassistant.components.heiman_home.button import (
    HeimanButtonEntity,
    async_setup_entry,
)
from homeassistant.components.heiman_home.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_button_setup(hass: HomeAssistant, setup_credentials: None) -> None:
    """Test button platform setup."""
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


async def test_button_entity_creation(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test button entity creation from device properties."""
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

    mute_prop = DeviceProperty(
        identifier="mute",
        name="Mute",
        value=1,
        data_type="bool",
        writable=True,
        entity="button",
    )

    mock_device.properties = {"mute": mute_prop}
    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    # Initialize DOMAIN data before calling async_setup_entry
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    assert len(added_entities) == 1
    button = added_entities[0]
    assert button.unique_id == "device-1_mute_button"
    assert button.name == "Mute"


async def test_button_entity_available_property(hass: HomeAssistant) -> None:
    """Test button entity available property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "mute": DeviceProperty(
            identifier="mute", name="Mute", value=1, writable=True
        )
    }

    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="mute",
    )

    assert button.available is True

    mock_device.online = False
    assert button.available is False

    mock_coordinator.get_device.return_value = None
    assert button.available is False

    mock_device.online = True
    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.last_update_success = False
    assert button.available is False


async def test_button_entity_device_info(hass: HomeAssistant) -> None:
    """Test button entity device info."""
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
        "mute": DeviceProperty(
            identifier="mute", name="Mute", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="mute",
    )

    device_info = button.device_info
    assert device_info is not None
    assert device_info["name"] == "Test Device"
    assert device_info["manufacturer"] == "Heiman"
    assert device_info["model"] == "HS1"
    assert device_info["sw_version"] == "1.0"
    assert device_info["hw_version"] == "1.0"
    assert (DOMAIN, "device-1") in device_info["identifiers"]


async def test_button_entity_unique_id(hass: HomeAssistant) -> None:
    """Test button entity unique ID."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-123"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "mute": DeviceProperty(
            identifier="mute", name="Mute", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="mute",
    )

    assert button.unique_id == "device-123_mute_button"


async def test_button_entity_has_entity_name(hass: HomeAssistant) -> None:
    """Test button entity has entity name."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "My Gateway"
    mock_device.online = True
    mock_device.properties = {
        "mute": DeviceProperty(
            identifier="mute", name="Mute", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="mute",
    )

    assert button.has_entity_name is True


async def test_button_entity_async_press(hass: HomeAssistant) -> None:
    """Test button async_press method."""
    mock_coordinator = MagicMock()
    mock_mqtt_client = AsyncMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.product_id = "prod-1"
    mock_device.raw_data = {
        "deviceType": "sensor",
        "parentId": None,
    }
    mock_device.properties = {
        "mute": DeviceProperty(
            identifier="mute", name="Mute", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.mqtt_client = mock_mqtt_client

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="mute",
    )

    await button.async_press()

    mock_mqtt_client.async_write_property.assert_called_once_with(
        device_id="device-1",
        product_id="prod-1",
        property_identifiers=["mute"],
        values={"mute": 1},
        device_info={
            "deviceType": "sensor",
            "parentId": None,
        },
    )


async def test_button_entity_async_press_no_device(hass: HomeAssistant) -> None:
    """Test button async_press when device is not found."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "mute": DeviceProperty(
            identifier="mute", name="Mute", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="mute",
    )

    mock_coordinator.get_device.return_value = None
    mock_coordinator.mqtt_client = MagicMock()

    await button.async_press()

    assert not mock_coordinator.mqtt_client.async_write_property.called


async def test_button_entity_async_press_no_property(hass: HomeAssistant) -> None:
    """Test button async_press when property is not found."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {}

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="mute",
    )

    mock_coordinator.mqtt_client = AsyncMock()

    await button.async_press()

    assert not mock_coordinator.mqtt_client.async_write_property.called


async def test_button_entity_async_press_default_value(hass: HomeAssistant) -> None:
    """Test button async_press with default value when property value is None."""
    mock_coordinator = MagicMock()
    mock_mqtt_client = AsyncMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.product_id = "prod-1"
    mock_device.raw_data = {
        "deviceType": "sensor",
        "parentId": None,
    }
    mock_device.properties = {
        "mute": DeviceProperty(
            identifier="mute", name="Mute", value=None, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.mqtt_client = mock_mqtt_client

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="mute",
    )

    await button.async_press()

    mock_mqtt_client.async_write_property.assert_called_once_with(
        device_id="device-1",
        product_id="prod-1",
        property_identifiers=["mute"],
        values={"mute": 1},
        device_info={
            "deviceType": "sensor",
            "parentId": None,
        },
    )


async def test_button_entity_extra_state_attributes(hass: HomeAssistant) -> None:
    """Test button entity extra_state_attributes property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "mute": DeviceProperty(
            identifier="mute",
            name="Mute",
            value=1,
            writable=True,
            unit="units",
            data_type="bool",
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="mute",
    )

    attrs = button.extra_state_attributes
    assert attrs is not None
    assert attrs.get("unit") == "units"
    assert attrs.get("data_type") == "bool"
    assert attrs.get("raw_value") == 1

    # Test when device is not found - should return empty dict
    mock_coordinator.get_device.return_value = None
    attrs = button.extra_state_attributes
    assert attrs == {}


async def test_button_entity_extra_state_attributes_property_not_found(
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

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="mute",
    )

    attrs = button.extra_state_attributes
    assert attrs == {}


async def test_button_entity_name_fallback(hass: HomeAssistant) -> None:
    """Test button entity name fallback to property identifier."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {}

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="unknown_button",
    )

    assert button.name == "unknown_button"


async def test_button_icon_led(hass: HomeAssistant) -> None:
    """Test icon for LED button."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "led_indicator": DeviceProperty(
            identifier="led_indicator", name="LED Indicator", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="led_indicator",
    )

    assert button.icon == "mdi:led-on"


async def test_button_icon_locate(hass: HomeAssistant) -> None:
    """Test icon for locate button."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "locate_device": DeviceProperty(
            identifier="locate_device", name="Locate Device", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="locate_device",
    )

    assert button.icon == "mdi:radar"


async def test_button_icon_mute(hass: HomeAssistant) -> None:
    """Test icon for mute button."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "mute": DeviceProperty(
            identifier="mute", name="Mute", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="mute",
    )

    assert button.icon == "mdi:volume-mute"


async def test_button_icon_test(hass: HomeAssistant) -> None:
    """Test icon for test button."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "self_test": DeviceProperty(
            identifier="self_test", name="Self Test", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="self_test",
    )

    assert button.icon == "mdi:clipboard-check-outline"


async def test_button_icon_power(hass: HomeAssistant) -> None:
    """Test icon for power button."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "power_switch": DeviceProperty(
            identifier="power_switch", name="Power Switch", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power_switch",
    )

    assert button.icon == "mdi:power-socket"


async def test_button_icon_default(hass: HomeAssistant) -> None:
    """Test default icon for unknown button type."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "unknown_button": DeviceProperty(
            identifier="unknown_button", name="Unknown Button", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="unknown_button",
    )

    assert button.icon == "mdi:toggle-switch"


async def test_button_entity_deduplication(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test button entity deduplication within a single call."""
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

    mute_prop = DeviceProperty(
        identifier="mute",
        name="Mute",
        value=1,
        data_type="bool",
        writable=True,
        entity="button",
    )

    mock_device.properties = {"mute": mute_prop}
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

    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    # Verify entities are created (within a single call, deduplication happens)
    assert len(added_entities) == 1
    assert added_entities[0].unique_id == "device-1_mute_button"


async def test_button_creation_with_multiple_properties(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test button entity creation with multiple properties."""
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
    mock_device.device_name = "Multi Button Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS2"
    mock_device.product_id = "prod-2"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    mute_prop = DeviceProperty(
        identifier="mute",
        name="Mute",
        value=1,
        data_type="bool",
        writable=True,
        entity="button",
    )

    test_prop = DeviceProperty(
        identifier="self_test",
        name="Self Test",
        value=1,
        data_type="bool",
        writable=True,
        entity="button",
    )

    non_button_prop = DeviceProperty(
        identifier="temperature",
        name="Temperature",
        value=25.5,
        data_type="float",
        readable=True,
        entity="sensor",
    )

    mock_device.properties = {
        "mute": mute_prop,
        "self_test": test_prop,
        "temperature": non_button_prop,
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
    unique_ids = {button.unique_id for button in added_entities}
    assert "device-1_mute_button" in unique_ids
    assert "device-1_self_test_button" in unique_ids


async def test_button_async_press_without_raw_data(hass: HomeAssistant) -> None:
    """Test button async_press when device has no raw_data."""
    mock_coordinator = MagicMock()
    mock_mqtt_client = AsyncMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.product_id = "prod-1"
    mock_device.device_type = "sensor"
    mock_device.parent_id = None
    mock_device.properties = {
        "mute": DeviceProperty(
            identifier="mute", name="Mute", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.mqtt_client = mock_mqtt_client

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="mute",
    )

    await button.async_press()

    mock_mqtt_client.async_write_property.assert_called_once_with(
        device_id="device-1",
        product_id="prod-1",
        property_identifiers=["mute"],
        values={"mute": 1},
        device_info={
            "deviceType": "sensor",
            "parentId": None,
        },
    )


async def test_button_icon_lowercase_matching(hass: HomeAssistant) -> None:
    """Test icon application with lowercase property identifier matching."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "Mute": DeviceProperty(
            identifier="Mute", name="Mute", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="Mute",
    )

    assert button.icon == "mdi:volume-mute"


async def test_button_icon_page(hass: HomeAssistant) -> None:
    """Test icon for page button."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "page": DeviceProperty(
            identifier="page", name="Page", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="page",
    )

    assert button.icon == "mdi:radar"


async def test_button_icon_find(hass: HomeAssistant) -> None:
    """Test icon for find button."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "find": DeviceProperty(
            identifier="find", name="Find", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="find",
    )

    assert button.icon == "mdi:radar"


async def test_button_is_button_property(hass: HomeAssistant) -> None:
    """Test _is_button_property function."""
    from homeassistant.components.heiman_home.button import _is_button_property

    # Non-writable property should return False
    non_writable_prop = DeviceProperty(
        identifier="test",
        name="Test",
        value=1,
        writable=False,
    )
    assert _is_button_property(non_writable_prop) is False

    # Bool data_type should return True
    bool_prop = DeviceProperty(
        identifier="test",
        name="Test",
        value=True,
        writable=True,
        data_type="bool",
    )
    assert _is_button_property(bool_prop) is True

    # Known button keywords should return True
    mute_prop = DeviceProperty(
        identifier="mute_button",
        name="Mute",
        value=1,
        writable=True,
        data_type="action",
    )
    assert _is_button_property(mute_prop) is True

    reset_prop = DeviceProperty(
        identifier="reset",
        name="Reset",
        value=1,
        writable=True,
    )
    assert _is_button_property(reset_prop) is True

    test_prop = DeviceProperty(
        identifier="selftest",
        name="Self Test",
        value=1,
        writable=True,
    )
    assert _is_button_property(test_prop) is True

    check_prop = DeviceProperty(
        identifier="check",
        name="Check",
        value=1,
        writable=True,
    )
    assert _is_button_property(check_prop) is True

    locate_prop = DeviceProperty(
        identifier="locate",
        name="Locate",
        value=1,
        writable=True,
    )
    assert _is_button_property(locate_prop) is True


async def test_button_icon_lowercase_match_led(hass: HomeAssistant) -> None:
    """Test button icon with test_led lowercase matching."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "test_led": DeviceProperty(
            identifier="test_led", name="Test LED", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="test_led",
    )

    # Should match "led" in lowercase
    assert button.icon == "mdi:led-on"


async def test_button_icon_exact_match(hass: HomeAssistant) -> None:
    """Test button icon exact match in ENTITY_ICONS."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Use property that has exact match in ENTITY_ICONS
    mock_device.properties = {
        "Mute": DeviceProperty(
            identifier="Mute", name="Mute", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="Mute",
    )

    # Exact match "Mute" in ENTITY_ICONS should use that icon
    assert button.icon == "mdi:volume-mute"


async def test_button_icon_no_match_fallback(hass: HomeAssistant) -> None:
    """Test button icon when no ENTITY_ICONS match."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Use property name that doesn't match any ENTITY_ICONS key
    mock_device.properties = {
        "custom_action": DeviceProperty(
            identifier="custom_action", name="Custom Action", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="custom_action",
    )

    # Should fall through to default icon (no match in ENTITY_ICONS)
    assert button.icon == "mdi:toggle-switch"


async def test_button_icon_lowercase_match_not_in_icons(hass: HomeAssistant) -> None:
    """Test button icon lowercase match when key not in ENTITY_ICONS."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Property with lowercase match not in ENTITY_ICONS
    mock_device.properties = {
        "LEDIndicator": DeviceProperty(
            identifier="LEDIndicator", name="LED Indicator", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="LEDIndicator",
    )

    # Original case "LEDIndicator" not in icons, lowercase "ledindicator" not in icons
    # Falls through to keyword matching: "led" matches -> mdi:led-on
    assert button.icon == "mdi:led-on"


async def test_button_icon_indicator_keyword(hass: HomeAssistant) -> None:
    """Test button icon with indicator keyword."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "Indicator": DeviceProperty(
            identifier="Indicator", name="Indicator", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="Indicator",
    )

    assert button.icon == "mdi:led-on"


async def test_button_icon_lowercase_match(hass: HomeAssistant) -> None:
    """Test button icon with uppercase property identifier that triggers lowercase matching."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Property with identifier that doesn't exist in icons
    # but lowercase "soundmute" exists as a lowercase-only variant in ENTITY_ICONS
    mock_device.properties = {
        "SoundMute": DeviceProperty(
            identifier="SoundMute", name="Sound Mute", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="SoundMute",
    )

    # First check "SoundMute" in icons -> False
    # Second check "soundmute" in icons -> True -> mdi:volume-mute
    assert button.icon == "mdi:volume-mute"


async def test_button_icon_mute_keyword_fallback(hass: HomeAssistant) -> None:
    """Test button icon with mute keyword in fallback branch."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-2"
    mock_device.device_name = "Test Device 2"
    mock_device.online = True
    # Property with identifier that doesn't exist in icons
    # lowercase doesn't exist either, but contains "mute" for fallback
    mock_device.properties = {
        "AudibleMute": DeviceProperty(
            identifier="AudibleMute", name="Audible Mute", value=1, writable=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    button = HeimanButtonEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AudibleMute",
    )

    # First check "AudibleMute" in icons -> False
    # Second check "audiblemute" in icons -> False
    # Fallback: "audiblemute" contains "mute" -> mdi:volume-mute
    assert button.icon == "mdi:volume-mute"
