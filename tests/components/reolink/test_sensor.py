"""Test the Reolink sensor platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.reolink import DEVICE_UPDATE_INTERVAL, const
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_NVR_NAME, TEST_UID

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor entities."""
    reolink_connect.ptz_pan_position.return_value = 1200
    reolink_connect.wifi_connection = True
    reolink_connect.wifi_signal = 3
    reolink_connect.hdd_list = [0]
    reolink_connect.hdd_storage.return_value = 95

    # enable the wifi_signal entity
    unique_id = f"{TEST_UID}_wifi_signal"
    entity_registry.async_get_or_create(
        domain=Platform.SENSOR,
        platform=const.DOMAIN,
        unique_id=unique_id,
        config_entry=config_entry,
        suggested_object_id=f"{TEST_NVR_NAME}_wi_fi_signal",
        disabled_by=None,
    )

    # enable the SD entity
    unique_id = f"{TEST_UID}_0_storage"
    entity_registry.async_get_or_create(
        domain=Platform.SENSOR,
        platform=const.DOMAIN,
        unique_id=unique_id,
        config_entry=config_entry,
        suggested_object_id=f"{TEST_NVR_NAME}_sd_0_storage",
        disabled_by=None,
    )

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SENSOR}.{TEST_NVR_NAME}_ptz_pan_position"
    assert hass.states.get(entity_id).state == "1200"

    entity_id = f"{Platform.SENSOR}.{TEST_NVR_NAME}_wi_fi_signal"
    assert hass.states.get(entity_id).state == "3"

    entity_id = f"{Platform.SENSOR}.{TEST_NVR_NAME}_sd_0_storage"
    assert hass.states.get(entity_id).state == "95"

    reolink_connect.hdd_available.return_value = False
    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_HDD_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test hdd sensor entity."""
    reolink_connect.hdd_list = [0]
    reolink_connect.hdd_type.return_value = "HDD"
    reolink_connect.hdd_storage.return_value = 85

    # enable the HDD entity
    unique_id = f"{TEST_UID}_0_storage"
    entity_registry.async_get_or_create(
        domain=Platform.SENSOR,
        platform=const.DOMAIN,
        unique_id=unique_id,
        config_entry=config_entry,
        suggested_object_id=f"{TEST_NVR_NAME}_hdd_0_storage",
        disabled_by=None,
    )

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SENSOR}.{TEST_NVR_NAME}_hdd_0_storage"
    assert hass.states.get(entity_id).state == "85"
