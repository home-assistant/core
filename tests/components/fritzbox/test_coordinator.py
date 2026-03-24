"""Tests for the AVM Fritz!Box integration."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

from pyfritzhome import LoginError
import pytest
from requests.exceptions import ConnectionError, HTTPError

from homeassistant.components.fritzbox.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utcnow

from . import (
    FritzDeviceCoverMock,
    FritzDeviceSensorMock,
    FritzDeviceSwitchMock,
    FritzEntityBaseMock,
    FritzTriggerMock,
    setup_config_entry,
)
from .const import MOCK_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_update_after_reboot(
    hass: HomeAssistant, fritz: Mock
) -> None:
    """Test coordinator after reboot."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG[DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)
    fritz().update_devices.side_effect = ["", HTTPError()]

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert fritz().update_devices.call_count == 1
    assert fritz().update_templates.call_count == 1
    assert fritz().get_devices.call_count == 1
    assert fritz().get_templates.call_count == 1
    assert fritz().login.call_count == 1

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=35))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_update_after_password_change(
    hass: HomeAssistant, fritz: Mock
) -> None:
    """Test coordinator after password change."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG[DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)
    fritz().login.side_effect = [LoginError("some_user")]

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_coordinator_update_when_unreachable(
    hass: HomeAssistant, fritz: Mock
) -> None:
    """Test coordinator after reboot."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG[DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)
    fritz().update_devices.side_effect = [ConnectionError()]

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
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
        domain=DOMAIN,
        data=MOCK_CONFIG[DOMAIN][CONF_DEVICES][0],
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


async def test_coordinator_workaround_sub_units_without_main_device(
    hass: HomeAssistant,
    fritz: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the workaround for sub units without main device."""
    fritz().get_devices.return_value = [
        FritzDeviceSensorMock(
            ain="bad_device-1",
            device_and_unit_id=("bad_device", "1"),
            name="bad_sensor_sub",
        ),
        FritzDeviceSensorMock(
            ain="good_device",
            device_and_unit_id=("good_device", None),
            name="good_sensor",
        ),
        FritzDeviceSensorMock(
            ain="good_device-1",
            device_and_unit_id=("good_device", "1"),
            name="good_sensor_sub",
        ),
    ]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG[DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert len(device_entries) == 2
    assert device_entries[0].identifiers == {(DOMAIN, "good_device")}
    assert device_entries[1].identifiers == {(DOMAIN, "bad_device")}


async def test_coordinator_cleanup_ain_with_underscore(
    hass: HomeAssistant,
    fritz: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test cleanup does not wrongly remove entities for devices with underscore in AIN.

    The old split("_")[0] check extracted only the first segment of an AIN
    containing underscores, causing active entities to be removed incorrectly.
    """
    device_underscore = FritzDeviceSwitchMock(
        ain="fake_ain_switch",
        device_and_unit_id=("fake_ain_switch", None),
        name="fake_switch_underscore",
    )
    device_normal = FritzDeviceSwitchMock(
        ain="fake ain cover",
        device_and_unit_id=("fake ain cover", None),
        name="fake_switch_normal",
    )
    fritz().get_devices.return_value = [device_underscore, device_normal]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG[DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    count_before = len(
        er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    )
    assert count_before > 0

    # Remove device_normal to trigger cleanup_removed_devices()
    fritz().get_devices.return_value = [device_underscore]
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=35))
    await hass.async_block_till_done(wait_background_tasks=True)

    remaining = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert all("fake_ain_switch" in e.unique_id for e in remaining)
    assert not any("fake ain cover" in e.unique_id for e in remaining)


async def test_coordinator_cleanup_preserves_trigger_entities(
    hass: HomeAssistant,
    fritz: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that trigger entities are not wrongly removed when a device is deleted.

    The old cleanup code only included devices and templates in available_ains,
    so trigger AINs were never found and trigger entities were deleted on every
    cleanup run, even when the trigger itself was still active.
    """
    fritz().get_triggers.return_value = [FritzTriggerMock()]
    fritz().get_devices.return_value = [
        FritzDeviceSwitchMock(
            ain="fake ain switch 1",
            device_and_unit_id=("fake ain switch 1", None),
            name="fake_switch_1",
        ),
        FritzDeviceSwitchMock(
            ain="fake ain switch 2",
            device_and_unit_id=("fake ain switch 2", None),
            name="fake_switch_2",
        ),
    ]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG[DOMAIN][CONF_DEVICES][0],
        unique_id="any",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    trigger_entities_before = [
        e
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if FritzTriggerMock.ain in e.unique_id
    ]
    assert len(trigger_entities_before) == 1

    # Remove one device to trigger cleanup_removed_devices()
    fritz().get_devices.return_value = [
        FritzDeviceSwitchMock(
            ain="fake ain switch 1",
            device_and_unit_id=("fake ain switch 1", None),
            name="fake_switch_1",
        ),
    ]
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=35))
    await hass.async_block_till_done(wait_background_tasks=True)

    trigger_entities_after = [
        e
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if FritzTriggerMock.ain in e.unique_id
    ]
    assert len(trigger_entities_after) == 1


@pytest.mark.parametrize(
    ("trigger", "side_effect", "switch_entity_count"),
    [
        (None, None, 0),
        (None, HTTPError(), 0),
        (FritzTriggerMock(), None, 1),
    ],
)
async def test_coordinator_has_triggers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    fritz: Mock,
    trigger: Mock | None,
    side_effect: Exception | None,
    switch_entity_count: int,
) -> None:
    """Test coordinator has_triggers property."""
    fritz().has_triggers.side_effect = side_effect
    assert await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], fritz=fritz, trigger=trigger
    )
    assert len(hass.states.async_all(SWITCH_DOMAIN)) == switch_entity_count
