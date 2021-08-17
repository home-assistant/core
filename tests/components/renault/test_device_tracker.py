"""Tests for Renault sensors."""
from unittest.mock import patch

import pytest
from renault_api.kamereon import exceptions

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.setup import async_setup_component

from . import (
    setup_renault_integration_vehicle,
    setup_renault_integration_vehicle_with_no_data,
    setup_renault_integration_vehicle_with_side_effect,
)
from .const import MOCK_VEHICLES

from tests.common import mock_device_registry, mock_registry


@pytest.mark.parametrize("vehicle_type", MOCK_VEHICLES.keys())
async def test_device_trackers(hass, vehicle_type):
    """Test for Renault device trackers."""
    await async_setup_component(hass, "persistent_notification", {})
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    with patch("homeassistant.components.renault.PLATFORMS", [DEVICE_TRACKER_DOMAIN]):
        await setup_renault_integration_vehicle(hass, vehicle_type)
        await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    expected_entities = mock_vehicle[DEVICE_TRACKER_DOMAIN]
    if len(expected_entities) == 0:
        assert len(device_registry.devices) == 0
        assert len(entity_registry.entities) == 0
        return

    assert len(device_registry.devices) == 1
    expected_device = mock_vehicle["expected_device"]
    registry_entry = device_registry.async_get_device(expected_device[ATTR_IDENTIFIERS])
    assert registry_entry is not None
    assert registry_entry.identifiers == expected_device[ATTR_IDENTIFIERS]
    assert registry_entry.manufacturer == expected_device[ATTR_MANUFACTURER]
    assert registry_entry.name == expected_device[ATTR_NAME]
    assert registry_entry.model == expected_device[ATTR_MODEL]
    assert registry_entry.sw_version == expected_device[ATTR_SW_VERSION]

    assert len(entity_registry.entities) == len(expected_entities)
    for expected_entity in expected_entities:
        entity_id = expected_entity["entity_id"]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_entity["unique_id"]
        assert registry_entry.unit_of_measurement == expected_entity.get("unit")
        assert registry_entry.device_class == expected_entity.get("class")
        state = hass.states.get(entity_id)
        assert state.state == expected_entity["result"]


@pytest.mark.parametrize("vehicle_type", MOCK_VEHICLES.keys())
async def test_device_tracker_empty(hass, vehicle_type):
    """Test for Renault device trackers with empty data from Renault."""
    await async_setup_component(hass, "persistent_notification", {})
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    with patch("homeassistant.components.renault.PLATFORMS", [DEVICE_TRACKER_DOMAIN]):
        await setup_renault_integration_vehicle_with_no_data(hass, vehicle_type)
        await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    expected_entities = mock_vehicle[DEVICE_TRACKER_DOMAIN]
    if len(expected_entities) == 0:
        assert len(device_registry.devices) == 0
        assert len(entity_registry.entities) == 0
        return

    assert len(device_registry.devices) == 1
    expected_device = mock_vehicle["expected_device"]
    registry_entry = device_registry.async_get_device(expected_device[ATTR_IDENTIFIERS])
    assert registry_entry is not None
    assert registry_entry.identifiers == expected_device[ATTR_IDENTIFIERS]
    assert registry_entry.manufacturer == expected_device[ATTR_MANUFACTURER]
    assert registry_entry.name == expected_device[ATTR_NAME]
    assert registry_entry.model == expected_device[ATTR_MODEL]
    assert registry_entry.sw_version == expected_device[ATTR_SW_VERSION]

    assert len(entity_registry.entities) == len(expected_entities)
    for expected_entity in expected_entities:
        entity_id = expected_entity["entity_id"]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_entity["unique_id"]
        assert registry_entry.unit_of_measurement == expected_entity.get("unit")
        assert registry_entry.device_class == expected_entity.get("class")
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("vehicle_type", MOCK_VEHICLES.keys())
async def test_device_tracker_errors(hass, vehicle_type):
    """Test for Renault device trackers with temporary failure."""
    await async_setup_component(hass, "persistent_notification", {})
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    invalid_upstream_exception = exceptions.InvalidUpstreamException(
        "err.tech.500",
        "Invalid response from the upstream server (The request sent to the GDC is erroneous) ; 502 Bad Gateway",
    )

    with patch("homeassistant.components.renault.PLATFORMS", [DEVICE_TRACKER_DOMAIN]):
        await setup_renault_integration_vehicle_with_side_effect(
            hass, vehicle_type, invalid_upstream_exception
        )
        await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    expected_entities = mock_vehicle[DEVICE_TRACKER_DOMAIN]
    if len(expected_entities) == 0:
        assert len(device_registry.devices) == 0
        assert len(entity_registry.entities) == 0
        return

    assert len(device_registry.devices) == 1
    expected_device = mock_vehicle["expected_device"]
    registry_entry = device_registry.async_get_device(expected_device[ATTR_IDENTIFIERS])
    assert registry_entry is not None
    assert registry_entry.identifiers == expected_device[ATTR_IDENTIFIERS]
    assert registry_entry.manufacturer == expected_device[ATTR_MANUFACTURER]
    assert registry_entry.name == expected_device[ATTR_NAME]
    assert registry_entry.model == expected_device[ATTR_MODEL]
    assert registry_entry.sw_version == expected_device[ATTR_SW_VERSION]

    assert len(entity_registry.entities) == len(expected_entities)
    for expected_entity in expected_entities:
        entity_id = expected_entity["entity_id"]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_entity["unique_id"]
        assert registry_entry.unit_of_measurement == expected_entity.get("unit")
        assert registry_entry.device_class == expected_entity.get("class")
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE


async def test_device_tracker_access_denied(hass):
    """Test for Renault device trackers with access denied failure."""
    await async_setup_component(hass, "persistent_notification", {})
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    access_denied_exception = exceptions.AccessDeniedException(
        "err.func.403",
        "Access is denied for this resource",
    )

    with patch("homeassistant.components.renault.PLATFORMS", [DEVICE_TRACKER_DOMAIN]):
        await setup_renault_integration_vehicle_with_side_effect(
            hass, "zoe_40", access_denied_exception
        )
        await hass.async_block_till_done()

    assert len(device_registry.devices) == 0
    assert len(entity_registry.entities) == 0


async def test_device_tracker_not_supported(hass):
    """Test for Renault device trackers with not supported failure."""
    await async_setup_component(hass, "persistent_notification", {})
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    not_supported_exception = exceptions.NotSupportedException(
        "err.tech.501",
        "This feature is not technically supported by this gateway",
    )

    with patch("homeassistant.components.renault.PLATFORMS", [DEVICE_TRACKER_DOMAIN]):
        await setup_renault_integration_vehicle_with_side_effect(
            hass, "zoe_40", not_supported_exception
        )
        await hass.async_block_till_done()

    assert len(device_registry.devices) == 0
    assert len(entity_registry.entities) == 0
