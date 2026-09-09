"""Test RainMachine switches."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rainmachine.const import (
    CONF_DEFAULT_ZONE_RUN_TIME,
    DOMAIN,
)
from homeassistant.components.rainmachine.services import (
    SERVICE_NAME_START_PROGRAM,
    SERVICE_NAME_START_ZONE,
    SERVICE_NAME_STOP_PROGRAM,
    SERVICE_NAME_STOP_ZONE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, snapshot_platform

PROGRAM_ENTITY_ID = "switch.12345_morning"
ZONE_ENTITY_ID = "switch.12345_landscaping"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switches(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
) -> None:
    """Test switches."""
    with (
        patch("homeassistant.components.rainmachine.Client", return_value=client),
        patch("homeassistant.components.rainmachine.PLATFORMS", [Platform.SWITCH]),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_activity_services(
    hass: HomeAssistant,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
    controller: AsyncMock,
) -> None:
    """Test program and zone services continue to target activity switches."""
    with (
        patch("homeassistant.components.rainmachine.Client", return_value=client),
        patch("homeassistant.components.rainmachine.PLATFORMS", [Platform.SWITCH]),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAME_START_PROGRAM,
        {ATTR_ENTITY_ID: PROGRAM_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    controller.programs.start.assert_awaited_once_with(1)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAME_STOP_PROGRAM,
        {ATTR_ENTITY_ID: PROGRAM_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    controller.programs.stop.assert_awaited_once_with(1)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAME_START_ZONE,
        {
            ATTR_ENTITY_ID: ZONE_ENTITY_ID,
            CONF_DEFAULT_ZONE_RUN_TIME: 300,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    controller.zones.start.assert_awaited_once_with(1, 300)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAME_STOP_ZONE,
        {ATTR_ENTITY_ID: ZONE_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    controller.zones.stop.assert_awaited_once_with(1)
