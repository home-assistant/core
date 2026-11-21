"""Tests for the Infrared consumer entity helpers."""

import pytest
from pytest_homeassistant.common import MockConfigEntry, MockEntityPlatform
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

TEST_DOMAIN = "test"
CONSUMER_IDENTIFIER = (TEST_DOMAIN, "consumer")


class MockConsumerEntity(InfraredEmitterConsumerEntity):
    """Mock infrared emitter consumer entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_unique_id = "consumer"
    _attr_device_info = dr.DeviceInfo(
        identifiers={CONSUMER_IDENTIFIER}, name="Test consumer"
    )
    _infrared_emitter_entity_id = EMITTER_ENTITY_ID


class MockLinkedConsumerEntity(MockConsumerEntity):
    """Mock consumer entity whose integration sets the via device itself."""

    _attr_device_info = dr.DeviceInfo(
        identifiers={CONSUMER_IDENTIFIER}, name="Test consumer", via_device_id=None
    )


@pytest.fixture
def consumer_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the consumer integration's config entry."""
    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def consumer_platform(
    hass: HomeAssistant, consumer_config_entry: MockConfigEntry
) -> MockEntityPlatform:
    """Return the entity platform of the consumer integration."""
    platform = MockEntityPlatform(hass, domain="button", platform_name=TEST_DOMAIN)
    platform.config_entry = consumer_config_entry
    return platform


@pytest.fixture
def emitter_device(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> dr.DeviceEntry:
    """Put the infrared emitter entity on a device."""
    emitter_config_entry = MockConfigEntry(domain="emitter")
    emitter_config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=emitter_config_entry.entry_id,
        identifiers={("emitter", "blaster")},
        name="IR blaster",
    )
    entity_registry.async_update_entity(EMITTER_ENTITY_ID, device_id=device.id)
    return device


async def test_via_device(
    device_registry: dr.DeviceRegistry,
    consumer_config_entry: MockConfigEntry,
    consumer_platform: MockEntityPlatform,
    emitter_device: dr.DeviceEntry,
) -> None:
    """Test the consumer device is linked to the emitter's device."""
    await consumer_platform.async_add_entities([MockConsumerEntity()])

    device = device_registry.async_get_device_by_identifier(
        CONSUMER_IDENTIFIER, consumer_config_entry.entry_id
    )
    assert device is not None
    assert device.via_device_id == emitter_device.id


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_via_device_emitter_without_device(
    device_registry: dr.DeviceRegistry,
    consumer_config_entry: MockConfigEntry,
    consumer_platform: MockEntityPlatform,
) -> None:
    """Test the consumer device is not linked when the emitter has no device."""
    await consumer_platform.async_add_entities([MockConsumerEntity()])

    device = device_registry.async_get_device_by_identifier(
        CONSUMER_IDENTIFIER, consumer_config_entry.entry_id
    )
    assert device is not None
    assert device.via_device_id is None


@pytest.mark.usefixtures("emitter_device")
async def test_via_device_set_by_integration(
    device_registry: dr.DeviceRegistry,
    consumer_config_entry: MockConfigEntry,
    consumer_platform: MockEntityPlatform,
) -> None:
    """Test a via device set by the integration is kept."""
    await consumer_platform.async_add_entities([MockLinkedConsumerEntity()])

    device = device_registry.async_get_device_by_identifier(
        CONSUMER_IDENTIFIER, consumer_config_entry.entry_id
    )
    assert device is not None
    assert device.via_device_id is None
