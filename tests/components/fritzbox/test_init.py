"""Tests for the AVM Fritz!Box integration."""

from __future__ import annotations

from unittest.mock import Mock, call, patch

from pyfritzhome import LoginError
import pytest
from requests.exceptions import ConnectionError as RequestConnectionError

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import FritzDeviceSwitchMock, setup_config_entry
from .const import CONF_FAKE_AIN, CONF_FAKE_NAME, MOCK_CONFIG

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_setup(hass: HomeAssistant, fritz: Mock) -> None:
    """Test setup of integration."""
    assert await setup_config_entry(hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0])
    entries = hass.config_entries.async_entries()
    assert entries
    assert len(entries) == 1
    assert entries[0].data[CONF_HOST] == "10.0.0.1"
    assert entries[0].data[CONF_PASSWORD] == "fake_pass"
    assert entries[0].data[CONF_USERNAME] == "fake_user"
    assert fritz.call_count == 1
    assert fritz.call_args_list == [
        call(host="10.0.0.1", password="fake_pass", user="fake_user")
    ]


@pytest.mark.parametrize(
    ("entitydata", "old_unique_id", "new_unique_id"),
    [
        (
            {
                "domain": SENSOR_DOMAIN,
                "platform": FB_DOMAIN,
                "unique_id": CONF_FAKE_AIN,
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
            },
            CONF_FAKE_AIN,
            f"{CONF_FAKE_AIN}_temperature",
        ),
        (
            {
                "domain": BINARY_SENSOR_DOMAIN,
                "platform": FB_DOMAIN,
                "unique_id": CONF_FAKE_AIN,
            },
            CONF_FAKE_AIN,
            f"{CONF_FAKE_AIN}_alarm",
        ),
    ],
)
async def test_update_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    fritz: Mock,
    entitydata: dict,
    old_unique_id: str,
    new_unique_id: str,
) -> None:
    """Test unique_id update of integration."""
    fritz().get_devices.return_value = [FritzDeviceSwitchMock()]
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == new_unique_id


@pytest.mark.parametrize(
    ("entitydata", "unique_id"),
    [
        (
            {
                "domain": SENSOR_DOMAIN,
                "platform": FB_DOMAIN,
                "unique_id": f"{CONF_FAKE_AIN}_temperature",
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
            },
            f"{CONF_FAKE_AIN}_temperature",
        ),
        (
            {
                "domain": BINARY_SENSOR_DOMAIN,
                "platform": FB_DOMAIN,
                "unique_id": f"{CONF_FAKE_AIN}_alarm",
            },
            f"{CONF_FAKE_AIN}_alarm",
        ),
        (
            {
                "domain": BINARY_SENSOR_DOMAIN,
                "platform": FB_DOMAIN,
                "unique_id": f"{CONF_FAKE_AIN}_other",
            },
            f"{CONF_FAKE_AIN}_other",
        ),
    ],
)
async def test_update_unique_id_no_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    fritz: Mock,
    entitydata: dict,
    unique_id: str,
) -> None:
    """Test unique_id is not updated of integration."""
    fritz().get_devices.return_value = [FritzDeviceSwitchMock()]
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)

    entity = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=entry,
    )
    assert entity.unique_id == unique_id
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == unique_id


async def test_unload_remove(hass: HomeAssistant, fritz: Mock) -> None:
    """Test unload and remove of integration."""
    fritz().get_devices.return_value = [FritzDeviceSwitchMock()]
    entity_id = f"{SWITCH_DOMAIN}.{CONF_FAKE_NAME}"

    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id=entity_id,
    )
    entry.add_to_hass(hass)

    config_entries = hass.config_entries.async_entries(FB_DOMAIN)
    assert len(config_entries) == 1
    assert entry is config_entries[0]

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get(entity_id)
    assert state

    await hass.config_entries.async_unload(entry.entry_id)

    assert fritz().logout.call_count == 1
    assert entry.state is ConfigEntryState.NOT_LOADED
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert fritz().logout.call_count == 1
    assert entry.state is ConfigEntryState.NOT_LOADED
    state = hass.states.get(entity_id)
    assert state is None


async def test_logout_on_stop(hass: HomeAssistant, fritz: Mock) -> None:
    """Test we log out from fritzbox when Home Assistants stops."""
    fritz().get_devices.return_value = [FritzDeviceSwitchMock()]
    entity_id = f"{SWITCH_DOMAIN}.{CONF_FAKE_NAME}"

    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id=entity_id,
    )
    entry.add_to_hass(hass)

    config_entries = hass.config_entries.async_entries(FB_DOMAIN)
    assert len(config_entries) == 1
    assert entry is config_entries[0]

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get(entity_id)
    assert state

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert fritz().logout.call_count == 1


async def test_remove_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    fritz: Mock,
) -> None:
    """Test removing of a device."""
    assert await async_setup_component(hass, "config", {})
    assert await setup_config_entry(
        hass,
        MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        f"{FB_DOMAIN}.{CONF_FAKE_NAME}",
        FritzDeviceSwitchMock(),
        fritz,
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries()
    assert len(entries) == 1

    entry = entries[0]
    assert entry.supports_remove_device

    entity = entity_registry.async_get("switch.fake_name")
    good_device = device_registry.async_get(entity.device_id)

    orphan_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(FB_DOMAIN, "0000 000000")},
    )

    # try to delete good_device
    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(good_device.id, entry.entry_id)
    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    await hass.async_block_till_done()

    # try to delete orphan_device
    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(orphan_device.id, entry.entry_id)
    assert response["success"]
    await hass.async_block_till_done()


async def test_raise_config_entry_not_ready_when_offline(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_RETRY when fritzbox is offline."""
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data={CONF_HOST: "any", **MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0]},
        unique_id="any",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.fritzbox.coordinator.Fritzhome.login",
        side_effect=RequestConnectionError(),
    ) as mock_login:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        mock_login.assert_called_once()

    entries = hass.config_entries.async_entries()
    config_entry = entries[0]
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_raise_config_entry_error_when_login_fail(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_ERROR when login to fritzbox fail."""
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data={CONF_HOST: "any", **MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0]},
        unique_id="any",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.fritzbox.coordinator.Fritzhome.login",
        side_effect=LoginError("user"),
    ) as mock_login:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        mock_login.assert_called_once()

    entries = hass.config_entries.async_entries()
    config_entry = entries[0]
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
