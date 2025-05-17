"""Tests for the AVM Fritz!Box integration."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

from pyfritzhome import LoginError
from requests.exceptions import ConnectionError, HTTPError

from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utcnow

from . import FritzDeviceCoverMock, FritzDeviceSwitchMock, FritzEntityBaseMock
from .const import MOCK_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed


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
    assert fritz().update_templates.call_count == 1
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
    fritz().update_devices.side_effect = [ConnectionError(), ""]

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_automatic_registry_cleanup(
    hass: HomeAssistant,
    fritz: Mock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test automatic registry cleanup."""

    # init with 2 devices and 1 template
    fritz().get_devices.return_value = [
        FritzDeviceSwitchMock(
            ain="fake ain switch",
            device_and_unit_id=("fake ain switch", None),
            name="fake_switch",
        ),
        FritzDeviceCoverMock(
            ain="fake ain cover",
            device_and_unit_id=("fake ain cover", None),
            name="fake_cover",
        ),
    ]
    fritz().get_templates.return_value = [
        FritzEntityBaseMock(
            ain="fake ain template",
            device_and_unit_id=("fake ain template", None),
            name="fake_template",
        )
    ]
    entry = MockConfigEntry(
        domain=FB_DOMAIN,
        data=MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 20
    assert len(dr.async_entries_for_config_entry(device_registry, entry.entry_id)) == 3

    # remove one device, keep the template
    fritz().get_devices.return_value = [
        FritzDeviceSwitchMock(
            ain="fake ain switch",
            device_and_unit_id=("fake ain switch", None),
            name="fake_switch",
        )
    ]

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=35))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 13
    assert len(dr.async_entries_for_config_entry(device_registry, entry.entry_id)) == 2

    # remove the template, keep the device
    fritz().get_templates.return_value = []

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=35))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 12
    assert len(dr.async_entries_for_config_entry(device_registry, entry.entry_id)) == 1
