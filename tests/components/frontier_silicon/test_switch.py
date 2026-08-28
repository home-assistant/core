"""Test the Frontier Silicon switch entity."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock

from afsapi import FSConnectionError, FSNotImplementedError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

DST_SWITCH_ENTITY_ID = "switch.name_of_the_device_daylight_saving_time"


@pytest.mark.parametrize(
    ("dst_switch_side_effect", "expected_num_entities"),
    [(None, 2), (FSNotImplementedError, 1)],
)
async def test_init_with_dst_availability(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_afsapi: AsyncMock,
    dst_switch_side_effect: FSNotImplementedError | None,
    expected_num_entities: int,
) -> None:
    """Test integration setup notices the difference between devices which do or don't implement a DST switch."""
    mock_afsapi.get_dst.side_effect = dst_switch_side_effect

    await setup_integration(hass, config_entry)

    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device_entry = devices[0]

    entities = er.async_entries_for_device(entity_registry, device_entry.id)
    assert len(entities) == expected_num_entities


async def test_init_device_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_afsapi: AsyncMock,
) -> None:
    """Test that entity isn't added if there is a connection error."""
    mock_afsapi.get_dst.side_effect = FSConnectionError

    await setup_integration(hass, config_entry)

    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device_entry = devices[0]

    entities = er.async_entries_for_device(entity_registry, device_entry.id)
    expected_entities = 1
    assert len(entities) == expected_entities


async def test_init_device_not_ready_transient_connection_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_afsapi: AsyncMock,
) -> None:
    """Test that entity is added if there is a only a transient connection error."""

    def transient_connection_error_generator() -> Generator[FSConnectionError | bool]:
        """Generate a transient connection error, then always yield a good result."""
        yield FSConnectionError
        while True:
            yield True

    mock_afsapi.get_dst.side_effect = transient_connection_error_generator()
    await setup_integration(hass, config_entry)

    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device_entry = devices[0]

    entities = er.async_entries_for_device(entity_registry, device_entry.id)
    expected_entities = 2
    assert len(entities) == expected_entities


async def test_dst_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
) -> None:
    """Test turn_on and turn_off for DST switch."""

    # Set up integration
    await setup_integration(hass, config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: DST_SWITCH_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_afsapi.set_dst.assert_awaited_with(True)
    mock_afsapi.set_dst.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: DST_SWITCH_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_afsapi.set_dst.assert_awaited_with(False)
    mock_afsapi.set_dst.reset_mock()


async def test_dst_switch_get(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that switch state reflects get_dst result."""

    await setup_integration(hass, config_entry)

    # Turn DST switch on and advance time to trigger a poll
    mock_afsapi.get_dst.return_value = True
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(DST_SWITCH_ENTITY_ID).state == STATE_ON

    # Turn DST switch off and advance time to trigger a poll
    mock_afsapi.get_dst.return_value = False
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(DST_SWITCH_ENTITY_ID).state == STATE_OFF
