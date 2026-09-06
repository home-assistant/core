"""Test RainMachine valves."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rainmachine.const import (
    CONF_ALLOW_INACTIVE_ZONES_TO_RUN,
    CONF_DEFAULT_ZONE_RUN_TIME,
    DEFAULT_ZONE_RUN,
    DOMAIN,
)
from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, snapshot_platform


async def _async_setup_valves(
    hass: HomeAssistant,
    config: dict[str, Any],
    client: AsyncMock,
    *,
    load_switch: bool = False,
) -> None:
    """Set up only the RainMachine valve platform."""
    platforms = [Platform.SWITCH, Platform.VALVE] if load_switch else [Platform.VALVE]
    with (
        patch("homeassistant.components.rainmachine.Client", return_value=client),
        patch("homeassistant.components.rainmachine.PLATFORMS", platforms),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_valves(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
) -> None:
    """Test valves."""
    await _async_setup_valves(hass, config, client)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_valve_services(
    hass: HomeAssistant,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
    controller: AsyncMock,
) -> None:
    """Test opening and closing a zone valve."""
    await _async_setup_valves(hass, config, client, load_switch=True)

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_OPEN_VALVE,
        {ATTR_ENTITY_ID: "valve.12345_landscaping"},
        blocking=True,
    )
    controller.zones.start.assert_awaited_once_with(1, DEFAULT_ZONE_RUN)

    controller.zones.start.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        "start_zone",
        {
            ATTR_ENTITY_ID: "valve.12345_landscaping",
            CONF_DEFAULT_ZONE_RUN_TIME: 42,
        },
        blocking=True,
    )
    controller.zones.start.assert_awaited_once_with(1, 42)

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_CLOSE_VALVE,
        {ATTR_ENTITY_ID: "valve.12345_landscaping"},
        blocking=True,
    )
    controller.zones.stop.assert_awaited_once_with(1)


async def test_inactive_zone_cannot_open_by_default(
    hass: HomeAssistant,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
    controller: AsyncMock,
) -> None:
    """Test that an inactive zone cannot be opened by default."""
    await _async_setup_valves(hass, config, client)

    with pytest.raises(HomeAssistantError, match="Cannot open an inactive zone"):
        await hass.services.async_call(
            VALVE_DOMAIN,
            SERVICE_OPEN_VALVE,
            {ATTR_ENTITY_ID: "valve.12345_test"},
            blocking=True,
        )
    controller.zones.start.assert_not_awaited()


async def test_inactive_zone_can_open_when_allowed(
    hass: HomeAssistant,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
    controller: AsyncMock,
) -> None:
    """Test allowing inactive zones to run."""
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_ALLOW_INACTIVE_ZONES_TO_RUN: True},
    )
    await _async_setup_valves(hass, config, client)

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_OPEN_VALVE,
        {ATTR_ENTITY_ID: "valve.12345_test"},
        blocking=True,
    )
    controller.zones.start.assert_awaited_once_with(3, DEFAULT_ZONE_RUN)
