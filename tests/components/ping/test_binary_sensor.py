"""Test the binary sensor platform of ping."""

import asyncio
import contextlib
from datetime import timedelta
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
from icmplib import Host
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.ping.const import CONF_IMPORTED_BY, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_integration")
async def test_setup_and_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor setup and update."""

    # check if binary sensor is there
    entry = entity_registry.async_get("binary_sensor.10_10_10_10")
    assert entry == snapshot(exclude=props("unique_id"))

    state = hass.states.get("binary_sensor.10_10_10_10")
    assert state == snapshot

    # check if the sensor turns off.
    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host(address="10.10.10.10", packets_sent=10, rtts=[]),
    ):
        freezer.tick(timedelta(minutes=6))
        # pump the _async_update_data() task through its steps
        for _ in range(4):
            await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.10_10_10_10")
    assert state == snapshot


async def test_disabled_after_import(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test if binary sensor is disabled after import."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, data={CONF_IMPORTED_BY: "device_tracker"}
    )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # check if entity is disabled after import by device tracker
    entry = entity_registry.async_get("binary_sensor.10_10_10_10")
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("setup_integration")
async def test_never_delayed_long_enough_to_trigger_warning(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test handling of the early-return for slow pings."""
    entry = entity_registry.async_get("binary_sensor.10_10_10_10")

    never_return_task = asyncio.create_task(asyncio.Event().wait())
    mock_logger = Mock()

    # pretend the ping never resolves, to hit the limit
    # and then assert we didn't get any warnings about the limit being hit
    # (because the code handles it)
    with (
        patch(
            "homeassistant.components.ping.helpers.async_ping",
            new=lambda *args, **kwargs: never_return_task,
        ),
        patch(
            "homeassistant.helpers.entity._LOGGER",
            new=mock_logger,
        ),
    ):
        assert entry
        freezer.tick(timedelta(minutes=5))

        # pump the _async_update_data() task through its steps
        for _ in range(5):
            await hass.async_block_till_done()

    # no warnings emitted
    assert mock_logger.warning.call_count == 0

    # cleanup
    never_return_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await never_return_task
