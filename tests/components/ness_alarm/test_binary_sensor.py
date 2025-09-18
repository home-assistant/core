"""Test the Ness Alarm binary sensors."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.ness_alarm import CONF_NAME, SIGNAL_ZONE_CHANGED
from homeassistant.components.ness_alarm.const import (
    CONF_ID,
    CONF_MAX_SUPPORTED_ZONES,
    CONF_TYPE,
    CONF_ZONES,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import dispatcher, entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
            CONF_MAX_SUPPORTED_ZONES: 2,
        },
    )


@pytest.fixture
def mock_client():
    """Create a mock Ness client."""
    client = AsyncMock()
    client.keepalive = AsyncMock()
    client.update = AsyncMock()
    client.close = AsyncMock()
    return client


async def test_binary_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test binary sensor setup."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check that 2 zones were created
    state1 = hass.states.get("binary_sensor.zone_1")
    assert state1 is not None
    assert state1.name == "Zone 1"
    assert state1.state == STATE_OFF

    state2 = hass.states.get("binary_sensor.zone_2")
    assert state2 is not None
    assert state2.name == "Zone 2"
    assert state2.state == STATE_OFF


async def test_zone_state_changes(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test zone state changes."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Initial state
    assert hass.states.get("binary_sensor.zone_1").state == STATE_OFF
    assert hass.states.get("binary_sensor.zone_2").state == STATE_OFF

    # Trigger zone 1 via dispatcher directly
    dispatcher.async_dispatcher_send(hass, SIGNAL_ZONE_CHANGED, 1, True)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.zone_1").state == STATE_ON
    assert hass.states.get("binary_sensor.zone_2").state == STATE_OFF


async def test_zone_with_custom_device_class(
    hass: HomeAssistant,
    mock_client,
) -> None:
    """Test binary sensor with custom device class."""

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
            CONF_MAX_SUPPORTED_ZONES: 2,
            CONF_ZONES: [
                {
                    CONF_ID: 1,
                    CONF_NAME: "Door Sensor",
                    CONF_TYPE: BinarySensorDeviceClass.DOOR,
                },
                {
                    CONF_ID: 2,
                    CONF_NAME: "Window Sensor",
                    CONF_TYPE: BinarySensorDeviceClass.WINDOW,
                },
            ],
        },
    )
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check device classes
    state1 = hass.states.get("binary_sensor.door_sensor")
    assert state1 is not None
    assert state1.attributes.get("device_class") == BinarySensorDeviceClass.DOOR

    state2 = hass.states.get("binary_sensor.window_sensor")
    assert state2 is not None
    assert state2.attributes.get("device_class") == BinarySensorDeviceClass.WINDOW


async def test_zone_attributes(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test zone sensor attributes."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.zone_1")
    assert state is not None

    # Check zone_id attribute
    assert state.attributes.get("zone_id") == 1

    # Check device class default
    assert state.attributes.get("device_class") == "motion"


async def test_zone_ignore_irrelevant_changes(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test zone ignores state changes for other zones."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Initial state
    assert hass.states.get("binary_sensor.zone_1").state == STATE_OFF
    assert hass.states.get("binary_sensor.zone_2").state == STATE_OFF

    # Send zone 2 update
    dispatcher.async_dispatcher_send(hass, SIGNAL_ZONE_CHANGED, 2, True)
    await hass.async_block_till_done()

    # Zone 1 should remain OFF, Zone 2 should be ON
    assert hass.states.get("binary_sensor.zone_1").state == STATE_OFF
    assert hass.states.get("binary_sensor.zone_2").state == STATE_ON

    # Send zone 99 update (non-existent zone)
    dispatcher.async_dispatcher_send(hass, SIGNAL_ZONE_CHANGED, 99, True)
    await hass.async_block_till_done()

    # No zones should change
    assert hass.states.get("binary_sensor.zone_1").state == STATE_OFF
    assert hass.states.get("binary_sensor.zone_2").state == STATE_ON


async def test_all_32_zones_created(
    hass: HomeAssistant,
    mock_client,
) -> None:
    """Test that all 32 zones are created regardless of panel model."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
            "panel_model": "D8X",  # 8-zone panel
        },
    )
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    # Check all 32 zones exist in registry
    for zone_id in range(1, 33):
        unique_id = f"{mock_config_entry.entry_id}_zone_{zone_id}"
        entity_id = entity_registry.async_get_entity_id(
            "binary_sensor", DOMAIN, unique_id
        )
        assert entity_id is not None, f"Zone {zone_id} not found"

        # Check if enabled/disabled correctly
        entry = entity_registry.entities.get(entity_id)
        if zone_id <= 8:
            # Should be enabled for D8X
            assert entry.disabled_by is None
        else:
            # Should be disabled
            assert entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION


async def test_unknown_panel_model_defaults(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test unknown panel model defaults to 32 zones enabled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test", CONF_PORT: 2401},
    )
    entry.add_to_hass(hass)

    mock_client = AsyncMock()
    mock_client.get_panel_info.return_value = {"model": "UNKNOWN"}
    with patch("homeassistant.components.ness_alarm.Client", return_value=mock_client):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    for zone in range(1, 33):
        unique_id = f"{entry.entry_id}_zone_{zone}"
        ent_id = entity_registry.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
        assert ent_id is not None, f"Zone {zone} missing"
        entry_data = entity_registry.async_get(ent_id)
        assert entry_data.disabled_by is None


async def test_manual_zone_override(
    hass: HomeAssistant,
    mock_client,
) -> None:
    """Test manual zone count override."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
            "panel_model": "MANUAL_24",  # Manual override to 24 zones
        },
    )
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    # Check zones 1-24 are enabled, 25-32 are disabled
    for zone_id in range(1, 33):
        unique_id = f"{mock_config_entry.entry_id}_zone_{zone_id}"
        entity_id = entity_registry.async_get_entity_id(
            "binary_sensor", DOMAIN, unique_id
        )
        entry = entity_registry.entities.get(entity_id)

        if zone_id <= 24:
            assert entry.disabled_by is None
        else:
            assert entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION


async def test_zone_availability(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test zone sensors are always available."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # All zones should report as available
    for zone_id in range(1, 3):
        state = hass.states.get(f"binary_sensor.zone_{zone_id}")
        assert state is not None
        assert state.state != "unavailable"
