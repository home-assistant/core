"""Tests for device tracker entities."""
import pytest

from homeassistant.components.device_tracker.config_entry import (
    BaseTrackerEntity,
    ScannerEntity,
)
from homeassistant.components.device_tracker.const import (
    ATTR_HOST_NAME,
    ATTR_IP,
    ATTR_MAC,
    ATTR_SOURCE_TYPE,
    DOMAIN,
    SourceType,
)
from homeassistant.const import ATTR_BATTERY_LEVEL, STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_scanner_entity_device_tracker(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test ScannerEntity based device tracker."""
    # Make device tied to other integration so device tracker entities get enabled
    dr.async_get(hass).async_get_or_create(
        name="Device from other integration",
        config_entry_id=MockConfigEntry().entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "ad:de:ef:be:ed:fe")},
    )

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
    await hass.async_block_till_done()

    entity_id = "device_tracker.test_ad_de_ef_be_ed_fe"
    entity_state = hass.states.get(entity_id)
    assert entity_state.attributes == {
        ATTR_SOURCE_TYPE: SourceType.ROUTER,
        ATTR_BATTERY_LEVEL: 100,
        ATTR_IP: "0.0.0.0",
        ATTR_MAC: "ad:de:ef:be:ed:fe",
        ATTR_HOST_NAME: "test.hostname.org",
    }
    assert entity_state.state == STATE_NOT_HOME

    entity = hass.data[DOMAIN].get_entity(entity_id)
    entity.set_connected()
    await hass.async_block_till_done()

    entity_state = hass.states.get(entity_id)
    assert entity_state.state == STATE_HOME


def test_scanner_entity() -> None:
    """Test coverage for base ScannerEntity entity class."""
    entity = ScannerEntity()
    with pytest.raises(NotImplementedError):
        assert entity.source_type is None
    with pytest.raises(NotImplementedError):
        assert entity.is_connected is None
    with pytest.raises(NotImplementedError):
        assert entity.state == STATE_NOT_HOME
    assert entity.battery_level is None
    assert entity.ip_address is None
    assert entity.mac_address is None
    assert entity.hostname is None


def test_base_tracker_entity() -> None:
    """Test coverage for base BaseTrackerEntity entity class."""
    entity = BaseTrackerEntity()
    with pytest.raises(NotImplementedError):
        assert entity.source_type is None
    assert entity.battery_level is None
    with pytest.raises(NotImplementedError):
        assert entity.state_attributes is None
