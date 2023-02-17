"""Tests for the AVM Fritz!Box integration."""
from __future__ import annotations

from unittest.mock import Mock, call, patch
from xml.etree.ElementTree import ParseError

from pyfritzhome import LoginError
import pytest
from requests.exceptions import ConnectionError, HTTPError

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
    STATE_UNAVAILABLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import FritzDeviceSwitchMock, setup_config_entry
from .const import CONF_FAKE_AIN, CONF_FAKE_NAME, MOCK_CONFIG

from tests.common import MockConfigEntry


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
    fritz: Mock,
    entitydata: dict,
    old_unique_id: str,
    new_unique_id: str,
) -> None:
    """Test unique_id update of integration."""
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
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
    fritz: Mock,
    entitydata: dict,
    unique_id: str,
) -> None:
    """Test unique_id is not updated of integration."""
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
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


async def test_coordinator_update_after_reboot(
    hass: HomeAssistant, fritz: Mock
) -> None:
    """Test coordinator after reboot."""
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)
    fritz().update_devices.side_effect = [HTTPError(), ""]

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert fritz().update_devices.call_count == 2
    assert fritz().update_templates.call_count == 2
    assert fritz().get_devices.call_count == 1
    assert fritz().get_templates.call_count == 1
    assert fritz().login.call_count == 2


async def test_coordinator_update_after_password_change(
    hass: HomeAssistant, fritz: Mock
) -> None:
    """Test coordinator after password change."""
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)
    fritz().update_devices.side_effect = HTTPError()
    fritz().login.side_effect = ["", LoginError("some_user")]

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert fritz().update_devices.call_count == 1
    assert fritz().get_devices.call_count == 0
    assert fritz().get_templates.call_count == 0
    assert fritz().login.call_count == 2


async def test_coordinator_update_when_unreachable(
    hass: HomeAssistant, fritz: Mock
) -> None:
    """Test coordinator after reboot."""
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)
    fritz().get_devices.side_effect = [ConnectionError(), ""]

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


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


async def test_raise_config_entry_not_ready_when_offline(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_RETRY when fritzbox is offline."""
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data={CONF_HOST: "any", **MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0]},
        unique_id="any",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.fritzbox.Fritzhome.login",
        side_effect=LoginError("user"),
    ) as mock_login:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        mock_login.assert_called_once()

    entries = hass.config_entries.async_entries()
    config_entry = entries[0]
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_disable_smarthome_templates(hass: HomeAssistant, fritz: Mock) -> None:
    """Test smarthome templates are disabled."""
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)
    fritz().update_templates.side_effect = [ParseError(), ""]

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert fritz().update_templates.call_count == 1
