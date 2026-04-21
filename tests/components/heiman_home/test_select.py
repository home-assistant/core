"""Tests for the Heiman Home select platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from heimanconnect import DeviceProperty, HeimanDevice

from homeassistant.components.heiman_home.const import DOMAIN
from homeassistant.components.heiman_home.select import (
    HeimanSelectEntity,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_select_setup(hass: HomeAssistant, setup_credentials: None) -> None:
    """Test select platform setup."""
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


async def test_select_entity_creation(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test select entity creation from device properties."""
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

    alarm_sound_prop = DeviceProperty(
        identifier="AlarmSoundOption",
        name="Alarm Sound Option",
        value="1",
        data_type="enum",
        writable=True,
        entity="select",
    )

    mock_device.properties = {"AlarmSoundOption": alarm_sound_prop}
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
    select = added_entities[0]
    assert select.unique_id == "device-1_AlarmSoundOption_select"
    assert select.name == "Alarm Sound Option"


async def test_select_entity_available_property(hass: HomeAssistant) -> None:
    """Test select entity available property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    assert select.available is True

    mock_device.online = False
    assert select.available is False

    mock_coordinator.get_device.return_value = None
    assert select.available is False

    mock_device.online = True
    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.last_update_success = False
    assert select.available is False


async def test_select_entity_current_option(hass: HomeAssistant) -> None:
    """Test select entity current_option property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device
    # When coordinator has no cached value, current_option is None initially
    mock_coordinator.get_device_property.return_value = None

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    # Initial state depends on cache - if no cache value, it's None
    # After _update_current_option_from_cache is called, it should be "Medium Beep"
    mock_coordinator.get_device_property.return_value = "1"
    select._update_current_option_from_cache()
    assert select.current_option == "Medium Beep"


async def test_select_entity_device_info(hass: HomeAssistant) -> None:
    """Test select entity device info."""
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
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    device_info = select.device_info
    assert device_info is not None
    assert device_info["name"] == "Test Device"
    assert device_info["manufacturer"] == "Heiman"
    assert device_info["model"] == "HS1"
    assert device_info["sw_version"] == "1.0"
    assert device_info["hw_version"] == "1.0"
    assert (DOMAIN, "device-1") in device_info["identifiers"]


async def test_select_entity_unique_id(hass: HomeAssistant) -> None:
    """Test select entity unique ID."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-123"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    assert select.unique_id == "device-123_AlarmSoundOption_select"


async def test_select_entity_has_entity_name(hass: HomeAssistant) -> None:
    """Test select entity has entity name."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "My Gateway"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    assert select.has_entity_name is True


async def test_select_entity_options_alarm_sound(hass: HomeAssistant) -> None:
    """Test select entity options for AlarmSoundOption."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    assert len(select.options) == 3
    assert "Fast Beep" in select.options
    assert "Medium Beep" in select.options
    assert "Slow Beep" in select.options


async def test_select_entity_options_default(hass: HomeAssistant) -> None:
    """Test select entity options for default mode."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "arm_mode": DeviceProperty(identifier="arm_mode", name="Arm Mode", value="home")
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="arm_mode",
    )

    assert len(select.options) == 4
    assert "disarmed" in select.options
    assert "armed_home" in select.options
    assert "armed_away" in select.options
    assert "armed_night" in select.options


async def test_select_entity_async_select_option_alarm_sound(
    hass: HomeAssistant,
) -> None:
    """Test select entity async_select_option for AlarmSoundOption."""
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
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.mqtt_client = mock_mqtt_client

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    # Mock async_write_ha_state since entity is not added to hass
    select.async_write_ha_state = MagicMock()

    await select.async_select_option("Medium Beep")

    mock_mqtt_client.async_write_property.assert_called_once_with(
        device_id="device-1",
        product_id="prod-1",
        property_identifiers=["AlarmSoundOption"],
        values={"AlarmSoundOption": "1"},
        device_info={
            "deviceType": "sensor",
            "parentId": None,
        },
    )

    assert select.current_option == "Medium Beep"


async def test_select_entity_async_select_option_default_mode(
    hass: HomeAssistant,
) -> None:
    """Test select entity async_select_option for default mode."""
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
        "arm_mode": DeviceProperty(identifier="arm_mode", name="Arm Mode", value="home")
    }

    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.mqtt_client = mock_mqtt_client

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="arm_mode",
    )

    # Mock async_write_ha_state since entity is not added to hass
    select.async_write_ha_state = MagicMock()

    await select.async_select_option("armed_home")

    mock_mqtt_client.async_write_property.assert_called_once_with(
        device_id="device-1",
        product_id="prod-1",
        property_identifiers=["arm_mode"],
        values={"arm_mode": "home"},
        device_info={
            "deviceType": "sensor",
            "parentId": None,
        },
    )


async def test_select_entity_handle_coordinator_update(hass: HomeAssistant) -> None:
    """Test select entity _handle_coordinator_update method."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device
    # Set up initial cached value for __init__
    mock_coordinator.get_device_property.return_value = "1"

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    # Mock async_write_ha_state since entity is not added to hass
    select.async_write_ha_state = MagicMock()

    # Update the cached value for the coordinator update
    mock_coordinator.get_device_property.return_value = "2"
    select._handle_coordinator_update()

    assert select.current_option == "Slow Beep"
    # Verify async_write_ha_state was called
    select.async_write_ha_state.assert_called_once()


async def test_select_entity_extra_state_attributes(hass: HomeAssistant) -> None:
    """Test select entity extra_state_attributes property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption",
            name="Alarm Sound Option",
            value="1",
            unit="units",
            data_type="enum",
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    attrs = select.extra_state_attributes
    assert attrs is not None
    assert attrs.get("unit") == "units"
    assert attrs.get("data_type") == "enum"
    assert attrs.get("raw_value") == "1"

    # Test when device is not found - should return empty dict
    mock_coordinator.get_device.return_value = None
    attrs = select.extra_state_attributes
    assert attrs == {}


async def test_select_entity_extra_state_attributes_property_not_found(
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

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    attrs = select.extra_state_attributes
    assert attrs == {}


async def test_select_entity_name_fallback(hass: HomeAssistant) -> None:
    """Test select entity name fallback to property identifier."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {}

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="unknown_select",
    )

    assert select.name == "unknown_select"


async def test_select_icon_default(hass: HomeAssistant) -> None:
    """Test default icon for select entity."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "arm_mode": DeviceProperty(identifier="arm_mode", name="Arm Mode", value="home")
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="arm_mode",
    )

    assert select.icon == "mdi:volume-high"


async def test_select_get_description_alarm_sound(hass: HomeAssistant) -> None:
    """Test _get_description method for AlarmSoundOption."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    assert select._get_description("0") == "Fast Beep"
    assert select._get_description("1") == "Medium Beep"
    assert select._get_description("2") == "Slow Beep"
    assert select._get_description(0) == "Fast Beep"
    assert select._get_description(1) == "Medium Beep"
    assert select._get_description(2) == "Slow Beep"
    assert select._get_description(None) is None
    assert select._get_description("unknown") == "unknown"


async def test_select_get_value_alarm_sound(hass: HomeAssistant) -> None:
    """Test _get_value method for AlarmSoundOption."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    assert select._get_value("Fast Beep") == "0"
    assert select._get_value("Medium Beep") == "1"
    assert select._get_value("Slow Beep") == "2"


async def test_select_get_value_default_mode(hass: HomeAssistant) -> None:
    """Test _get_value method for default mode."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "arm_mode": DeviceProperty(identifier="arm_mode", name="Arm Mode", value="home")
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="arm_mode",
    )

    assert select._get_value("disarmed") == "disarmed"
    assert select._get_value("armed_home") == "home"
    assert select._get_value("armed_away") == "away"
    assert select._get_value("armed_night") == "night"


async def test_select_get_description_default_mode(hass: HomeAssistant) -> None:
    """Test _get_description method for default mode."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "arm_mode": DeviceProperty(identifier="arm_mode", name="Arm Mode", value="home")
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="arm_mode",
    )

    assert select._get_description("disarmed") == "disarmed"
    assert select._get_description("home") == "armed_home"
    assert select._get_description("away") == "armed_away"
    assert select._get_description("night") == "armed_night"


async def test_select_entity_deduplication(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test select entity deduplication within a single call."""
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

    alarm_sound_prop = DeviceProperty(
        identifier="AlarmSoundOption",
        name="Alarm Sound Option",
        value="1",
        data_type="enum",
        writable=True,
        entity="select",
    )

    mock_device.properties = {"AlarmSoundOption": alarm_sound_prop}
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

    # Verify entities are created (within a single call, deduplication happens)
    assert len(added_entities) == 1
    assert added_entities[0].unique_id == "device-1_AlarmSoundOption_select"


async def test_select_creation_with_multiple_properties(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test select entity creation with multiple properties."""
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
    mock_device.device_name = "Multi Select Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS2"
    mock_device.product_id = "prod-2"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    alarm_sound_prop = DeviceProperty(
        identifier="AlarmSoundOption",
        name="Alarm Sound Option",
        value="1",
        data_type="enum",
        writable=True,
        entity="select",
    )

    arm_mode_prop = DeviceProperty(
        identifier="arm_mode",
        name="Arm Mode",
        value="home",
        data_type="enum",
        writable=True,
        entity="select",
    )

    non_select_prop = DeviceProperty(
        identifier="temperature",
        name="Temperature",
        value=25.5,
        data_type="float",
        readable=True,
        entity="sensor",
    )

    mock_device.properties = {
        "AlarmSoundOption": alarm_sound_prop,
        "arm_mode": arm_mode_prop,
        "temperature": non_select_prop,
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
    unique_ids = {select.unique_id for select in added_entities}
    assert "device-1_AlarmSoundOption_select" in unique_ids
    assert "device-1_arm_mode_select" in unique_ids


async def test_select_async_select_option_without_raw_data(hass: HomeAssistant) -> None:
    """Test select async_select_option when device has no raw_data."""
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
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.mqtt_client = mock_mqtt_client

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    # Mock async_write_ha_state since entity is not added to hass
    select.async_write_ha_state = MagicMock()

    await select.async_select_option("Medium Beep")

    mock_mqtt_client.async_write_property.assert_called_once_with(
        device_id="device-1",
        product_id="prod-1",
        property_identifiers=["AlarmSoundOption"],
        values={"AlarmSoundOption": "1"},
        device_info={
            "deviceType": "sensor",
            "parentId": None,
        },
    )


async def test_select_update_current_option_from_cache(hass: HomeAssistant) -> None:
    """Test _update_current_option_from_cache method."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device
    # Set initial cached value for __init__ (will set _current_option to "Medium Beep")
    mock_coordinator.get_device_property.return_value = "1"

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    # Now update the cache to a different value
    mock_coordinator.get_device_property.return_value = "2"

    # Second call should detect the change and return True
    updated = select._update_current_option_from_cache()

    assert updated is True
    assert select.current_option == "Slow Beep"


async def test_select_update_current_option_from_cache_no_change(
    hass: HomeAssistant,
) -> None:
    """Test _update_current_option_from_cache when no change."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device
    # Cache returns "1" which maps to "Medium Beep"
    mock_coordinator.get_device_property.return_value = "1"

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    # Manually set current option to same value as cache
    select._current_option = "Medium Beep"

    # No change should happen
    mock_coordinator.get_device_property.return_value = "1"
    updated = select._update_current_option_from_cache()

    assert updated is False
    assert select.current_option == "Medium Beep"


async def test_select_icon_lowercase_matching(hass: HomeAssistant) -> None:
    """Test icon application with lowercase property identifier matching."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    assert select.icon == "mdi:volume-high"


async def test_select_get_description_fallback(hass: HomeAssistant) -> None:
    """Test _get_description fallback when value not in mapping."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    # Value not in reverse_value_list should return the value as string
    result = select._get_description("99")
    assert result == "99"


async def test_select_get_value_fallback(hass: HomeAssistant) -> None:
    """Test _get_value fallback when description not in mapping."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    # Description not in value_list should return the description itself
    result = select._get_value("Custom Option")
    assert result == "Custom Option"


async def test_select_icon_no_match_fallback(hass: HomeAssistant) -> None:
    """Test select icon when no ENTITY_ICONS match."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Use property that doesn't match any ENTITY_ICONS key
    mock_device.properties = {
        "CustomMode": DeviceProperty(
            identifier="CustomMode", name="Custom Mode", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="CustomMode",
    )

    # Should fall through to default icon
    assert select.icon == "mdi:volume-high"


async def test_select_icon_lowercase_match_alarmsoundoption(
    hass: HomeAssistant,
) -> None:
    """Test select icon with AlarmSoundOption lowercase matching."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    # Should match in ENTITY_ICONS
    assert select.icon == "mdi:volume-high"


async def test_select_icon_lowercase_match_not_in_icons(hass: HomeAssistant) -> None:
    """Test select icon lowercase match when key not in ENTITY_ICONS."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Property that has lowercase match but not in ENTITY_ICONS
    mock_device.properties = {
        "VOLUMEHIGH": DeviceProperty(
            identifier="VOLUMEHIGH", name="Volume High", value="high"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="VOLUMEHIGH",
    )

    # Original case not in icons, lowercase not in icons
    # Should fall through to default icon
    assert select.icon == "mdi:volume-high"


async def test_select_get_description_unknown_value(hass: HomeAssistant) -> None:
    """Test _get_description returns value as string for unknown values."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "AlarmSoundOption": DeviceProperty(
            identifier="AlarmSoundOption", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="AlarmSoundOption",
    )

    # Test value not in any mapping
    result = select._get_description("999")
    assert result == "999"


async def test_select_icon_exact_match(hass: HomeAssistant) -> None:
    """Test select icon exact match in ENTITY_ICONS."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Property with exact match in ENTITY_ICONS
    mock_device.properties = {
        "VolumeHigh": DeviceProperty(
            identifier="VolumeHigh", name="Volume High", value="high"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="VolumeHigh",
    )

    # Exact match should use that icon
    assert select.icon == "mdi:volume-high"


async def test_select_icon_lowercase_match_alarmsoundoption_uppercase(
    hass: HomeAssistant,
) -> None:
    """Test select icon with uppercase property identifier that triggers lowercase matching."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Property with uppercase identifier that does NOT exist in ENTITY_ICONS
    # but its lowercase form DOES exist
    mock_device.properties = {
        "ALARMSOUNDOPTION": DeviceProperty(
            identifier="ALARMSOUNDOPTION", name="Alarm Sound Option", value="1"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="ALARMSOUNDOPTION",
    )

    # First check "ALARMSOUNDOPTION" in icons -> False
    # Second check "alarmsoundoption" in icons -> True -> mdi:volume-high
    assert select.icon == "mdi:volume-high"


async def test_select_get_description_fallback_to_value_list(
    hass: HomeAssistant,
) -> None:
    """Test select _get_description fallback branch when reverse_value_list is incomplete."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "mode": DeviceProperty(identifier="mode", name="Mode", value="disarmed")
    }

    mock_coordinator.get_device.return_value = mock_device

    select = HeimanSelectEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="mode",
    )

    # Manually set _reverse_value_list to be incomplete
    # Only include "armed_away" but not "disarmed"
    select._reverse_value_list = {"armed_away": "armed_away"}

    # Call _get_description with value "disarmed"
    # First checks _reverse_value_list["disarmed"] -> KeyError
    # Falls back to _value_list iteration -> finds "disarmed"
    result = select._get_description("disarmed")

    # Should return description from _value_list iteration
    assert result == "disarmed"
