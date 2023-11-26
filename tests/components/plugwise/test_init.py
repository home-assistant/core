"""Tests for the Plugwise Climate integration."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from plugwise.exceptions import (
    ConnectionFailedError,
    InvalidAuthentication,
    InvalidXMLError,
    ResponseError,
    UnsupportedDeviceError,
)
import pytest

from homeassistant.components.plugwise.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

HA_PLUGWISE_SMILE = "homeassistant.components.plugwise.coordinator.Smile"
HA_PLUGWISE_SMILE_ASYNC_UPDATE = (
    "homeassistant.components.plugwise.coordinator.Smile.async_update"
)
HEATER_ID = "1cbf783bb11e4a7c8a6843dee3a86927"  # Opentherm device_id for migration
PLUG_ID = "cd0ddb54ef694e11ac18ed1cbce5dbbd"  # VCR device_id for migration
TOM = {
    "01234567890abcdefghijklmnopqrstu": {
        "available": True,
        "dev_class": "thermo_sensor",
        "firmware": "2020-11-04T01:00:00+01:00",
        "hardware": "1",
        "location": "f871b8c4d63549319221e294e4f88074",
        "model": "Tom/Floor",
        "name": "Tom Badkamer",
        "sensors": {
            "battery": 99,
            "temperature": 18.6,
            "temperature_difference": 2.3,
            "valve_position": 0.0,
        },
        "temperature_offset": {
            "lower_bound": -2.0,
            "resolution": 0.1,
            "setpoint": 0.1,
            "upper_bound": 2.0,
        },
        "vendor": "Plugwise",
        "zigbee_mac_address": "ABCD012345670A01",
    },
}


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smile_anna: MagicMock,
) -> None:
    """Test the Plugwise configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_smile_anna.connect.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "entry_state"),
    [
        (ConnectionFailedError, ConfigEntryState.SETUP_RETRY),
        (InvalidAuthentication, ConfigEntryState.SETUP_ERROR),
        (InvalidXMLError, ConfigEntryState.SETUP_RETRY),
        (ResponseError, ConfigEntryState.SETUP_RETRY),
        (UnsupportedDeviceError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_gateway_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smile_anna: MagicMock,
    side_effect: Exception,
    entry_state: ConfigEntryState,
) -> None:
    """Test the Plugwise configuration entry not ready."""
    mock_smile_anna.async_update.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(mock_smile_anna.connect.mock_calls) == 1
    assert mock_config_entry.state is entry_state


async def check_migration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entitydata: dict,
    old_unique_id: str,
    new_unique_id: str,
) -> None:
    """Helper-function for checking a unique_id migration."""
    mock_config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    entity: entity_registry.RegistryEntry = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=mock_config_entry,
    )
    assert entity.unique_id == old_unique_id
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == new_unique_id


@pytest.mark.parametrize(
    ("entitydata", "old_unique_id", "new_unique_id"),
    [
        (
            {
                "domain": SENSOR_DOMAIN,
                "platform": DOMAIN,
                "unique_id": f"{HEATER_ID}-outdoor_temperature",
                "suggested_object_id": f"{HEATER_ID}-outdoor_temperature",
                "disabled_by": None,
            },
            f"{HEATER_ID}-outdoor_temperature",
            f"{HEATER_ID}-outdoor_air_temperature",
        ),
    ],
)
async def test_migrate_unique_id_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entitydata: dict,
    old_unique_id: str,
    new_unique_id: str,
    mock_smile_anna: MagicMock,
) -> None:
    """Test migration of unique_id."""
    await check_migration(
        hass, mock_config_entry, entitydata, old_unique_id, new_unique_id
    )


@pytest.mark.parametrize(
    ("entitydata", "old_unique_id", "new_unique_id"),
    [
        (
            {
                "domain": SWITCH_DOMAIN,
                "platform": DOMAIN,
                "unique_id": f"{PLUG_ID}-plug",
                "suggested_object_id": f"{PLUG_ID}-plug",
                "disabled_by": None,
            },
            f"{PLUG_ID}-plug",
            f"{PLUG_ID}-relay",
        ),
    ],
)
async def test_migrate_unique_id_relay(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entitydata: dict,
    old_unique_id: str,
    new_unique_id: str,
    mock_smile_adam: MagicMock,
) -> None:
    """Test migration of unique_id."""
    await check_migration(
        hass, mock_config_entry, entitydata, old_unique_id, new_unique_id
    )


async def test_device_removal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smile_adam_2: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test a clean-up of the device_registry."""
    dev_reg = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(dev_reg, mock_config_entry.entry_id)
    assert len(devices) == 6
    item_list: list[str] = []
    for device_entry in list(dev_reg.devices.values()):
        for item in device_entry.identifiers:
            item_list.append(item[1])
    assert "1772a4ea304041adb83f357b751341ff" in item_list

    data = mock_smile_adam_2.async_update.return_value
    # Replace a Tom/Floor
    data.devices.pop("1772a4ea304041adb83f357b751341ff")
    data.devices.update(TOM)
    device_list = mock_smile_adam_2.device_list
    device_list.remove("1772a4ea304041adb83f357b751341ff")
    device_list.append("01234567890abcdefghijklmnopqrstu")
    with patch(HA_PLUGWISE_SMILE_ASYNC_UPDATE, return_value=data), patch(
        HA_PLUGWISE_SMILE, side_effect=device_list
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(minutes=1))
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(dev_reg, mock_config_entry.entry_id)
    item_list = []
    for device_entry in list(dev_reg.devices.values()):
        for item in device_entry.identifiers:
            item_list.append(item[1])
    assert "1772a4ea304041adb83f357b751341ff" not in item_list
