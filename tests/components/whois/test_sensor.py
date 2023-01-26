"""Tests for the sensors provided by the Whois integration."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.whois.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityCategory
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.freeze_time("2022-01-01 12:00:00", tz_offset=0)
async def test_whois_sensors(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Whois sensors."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.home_assistant_io_admin")
    entry = entity_registry.async_get("sensor.home_assistant_io_admin")
    assert entry
    assert state
    assert entry.unique_id == "home-assistant.io_admin"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "admin@example.com"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "home-assistant.io Admin"
    assert state.attributes.get(ATTR_ICON) == "mdi:account-star"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.home_assistant_io_created")
    entry = entity_registry.async_get("sensor.home_assistant_io_created")
    assert entry
    assert state
    assert entry.unique_id == "home-assistant.io_creation_date"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "2019-01-01T00:00:00+00:00"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "home-assistant.io Created"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.home_assistant_io_days_until_expiration")
    entry = entity_registry.async_get("sensor.home_assistant_io_days_until_expiration")
    assert entry
    assert state
    assert entry.unique_id == "home-assistant.io_days_until_expiration"
    assert entry.entity_category is None
    assert state.state == "364"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "home-assistant.io Days until expiration"
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:calendar-clock"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.home_assistant_io_expires")
    entry = entity_registry.async_get("sensor.home_assistant_io_expires")
    assert entry
    assert state
    assert entry.unique_id == "home-assistant.io_expiration_date"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "2023-01-01T00:00:00+00:00"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "home-assistant.io Expires"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.home_assistant_io_last_updated")
    entry = entity_registry.async_get("sensor.home_assistant_io_last_updated")
    assert entry
    assert state
    assert entry.unique_id == "home-assistant.io_last_updated"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "2021-12-31T23:00:00+00:00"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "home-assistant.io Last updated"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.home_assistant_io_owner")
    entry = entity_registry.async_get("sensor.home_assistant_io_owner")
    assert entry
    assert state
    assert entry.unique_id == "home-assistant.io_owner"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "owner@example.com"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "home-assistant.io Owner"
    assert state.attributes.get(ATTR_ICON) == "mdi:account"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.home_assistant_io_registrant")
    entry = entity_registry.async_get("sensor.home_assistant_io_registrant")
    assert entry
    assert state
    assert entry.unique_id == "home-assistant.io_registrant"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "registrant@example.com"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "home-assistant.io Registrant"
    assert state.attributes.get(ATTR_ICON) == "mdi:account-edit"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.home_assistant_io_registrar")
    entry = entity_registry.async_get("sensor.home_assistant_io_registrar")
    assert entry
    assert state
    assert entry.unique_id == "home-assistant.io_registrar"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "My Registrar"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "home-assistant.io Registrar"
    assert state.attributes.get(ATTR_ICON) == "mdi:store"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.home_assistant_io_reseller")
    entry = entity_registry.async_get("sensor.home_assistant_io_reseller")
    assert entry
    assert state
    assert entry.unique_id == "home-assistant.io_reseller"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "Top Domains, Low Prices"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "home-assistant.io Reseller"
    assert state.attributes.get(ATTR_ICON) == "mdi:store"
    assert ATTR_DEVICE_CLASS not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.configuration_url is None
    assert device_entry.entry_type == dr.DeviceEntryType.SERVICE
    assert device_entry.identifiers == {(DOMAIN, "home-assistant.io")}
    assert device_entry.name == "home-assistant.io"
    assert device_entry.manufacturer is None
    assert device_entry.model is None
    assert device_entry.sw_version is None


@pytest.mark.freeze_time("2022-01-01 12:00:00", tz_offset=0)
async def test_whois_sensors_missing_some_attrs(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: AsyncMock,
    init_integration_missing_some_attrs: MockConfigEntry,
) -> None:
    """Test the Whois sensors with owner and reseller missing."""
    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.home_assistant_io_last_updated")
    entry = entity_registry.async_get("sensor.home_assistant_io_last_updated")
    assert entry
    assert state
    assert entry.unique_id == "home-assistant.io_last_updated"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "2021-12-31T23:00:00+00:00"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "home-assistant.io Last updated"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert ATTR_ICON not in state.attributes

    assert hass.states.get("sensor.home_assistant_io_owner").state == STATE_UNKNOWN
    assert hass.states.get("sensor.home_assistant_io_reseller").state == STATE_UNKNOWN
    assert hass.states.get("sensor.home_assistant_io_registrant").state == STATE_UNKNOWN
    assert hass.states.get("sensor.home_assistant_io_admin").state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "entity_id",
    (
        "sensor.home_assistant_io_admin",
        "sensor.home_assistant_io_owner",
        "sensor.home_assistant_io_registrant",
        "sensor.home_assistant_io_registrar",
        "sensor.home_assistant_io_reseller",
    ),
)
async def test_disabled_by_default_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_id: str,
) -> None:
    """Test the disabled by default Whois sensors."""
    registry = er.async_get(hass)

    state = hass.states.get(entity_id)
    assert state is None

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize(
    "entity_id",
    (
        "sensor.home_assistant_io_admin",
        "sensor.home_assistant_io_created",
        "sensor.home_assistant_io_days_until_expiration",
        "sensor.home_assistant_io_expires",
        "sensor.home_assistant_io_last_updated",
        "sensor.home_assistant_io_owner",
        "sensor.home_assistant_io_registrant",
        "sensor.home_assistant_io_registrar",
        "sensor.home_assistant_io_reseller",
    ),
)
async def test_no_data(
    hass: HomeAssistant,
    mock_whois: MagicMock,
    entity_registry_enabled_by_default: AsyncMock,
    init_integration: MockConfigEntry,
    entity_id: str,
) -> None:
    """Test whois sensors become unknown when there is no data provided."""
    mock_whois.return_value = None

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
