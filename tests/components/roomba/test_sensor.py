"""Tests for IRobotEntity usage in Roomba sensor platform."""

import copy
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.roomba.const import CONF_BLID, CONF_CONTINUOUS, DOMAIN
from homeassistant.const import CONF_DELAY, CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


def _config_entry(blid: str) -> MockConfigEntry:
    """Return a config entry for an additional robot."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.0.30",
            CONF_BLID: blid,
            CONF_PASSWORD: "pass123",
        },
        options={CONF_CONTINUOUS: True, CONF_DELAY: 10},
        unique_id=blid,
    )


def _dock_tank_level_entities(hass: HomeAssistant) -> list[str]:
    """Return every dock tank level entity currently set up."""
    return sorted(
        entity_id
        for entity_id in hass.states.async_entity_ids(Platform.SENSOR)
        if "dock_tank_level" in entity_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test roomba entities."""
    with patch("homeassistant.components.roomba.PLATFORMS", [Platform.SENSOR]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_two_docked_robots_do_not_collide(
    hass: HomeAssistant,
    mock_roomba: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a second docked robot does not produce a duplicate dock sensor.

    The dock sensors used to be appended to the module level SENSORS list, so
    setting up a second docked robot appended them twice. The duplicate is
    dropped by the entity platform, so the surviving entity count still looks
    correct and only the logged error reveals the problem.
    """
    with patch("homeassistant.components.roomba.PLATFORMS", [Platform.SENSOR]):
        for blid in ("blid_first", "blid_second"):
            config_entry = _config_entry(blid)
            config_entry.add_to_hass(hass)
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

    assert "does not generate unique IDs" not in caplog.text
    assert len(_dock_tank_level_entities(hass)) == 2


async def test_robot_without_dock_has_no_dock_sensor(
    hass: HomeAssistant,
    mock_roomba: AsyncMock,
) -> None:
    """Test a robot without a dock does not get a dock sensor.

    A robot reporting no dock used to inherit one when it was set up after a
    robot that did have one.
    """
    docked_state = copy.deepcopy(mock_roomba.master_state)
    dockless_state = copy.deepcopy(mock_roomba.master_state)
    dockless_state["state"]["reported"]["dock"] = {}

    with patch("homeassistant.components.roomba.PLATFORMS", [Platform.SENSOR]):
        for blid, state in (
            ("blid_docked", docked_state),
            ("blid_dockless", dockless_state),
        ):
            mock_roomba.master_state = state
            config_entry = _config_entry(blid)
            config_entry.add_to_hass(hass)
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

    assert len(_dock_tank_level_entities(hass)) == 1
