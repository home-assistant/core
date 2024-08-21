"""Test the Teslemetry update platform."""

import copy
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion
from tesla_fleet_api.exceptions import VehicleOffline

from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.components.teslemetry.update import INSTALLING
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA, VEHICLE_DATA_ALT

from tests.common import async_fire_time_changed


async def test_update(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the update entities are correct."""

    entry = await setup_platform(hass, [Platform.UPDATE])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_update_alt(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data,
) -> None:
    """Tests that the update entities are correct."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    entry = await setup_platform(hass, [Platform.UPDATE])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_update_offline(
    hass: HomeAssistant,
    mock_vehicle_data,
) -> None:
    """Tests that the update entities are correct when offline."""

    mock_vehicle_data.side_effect = VehicleOffline
    await setup_platform(hass, [Platform.UPDATE])
    state = hass.states.get("update.test_update")
    assert state.state == STATE_UNKNOWN


async def test_update_services(
    hass: HomeAssistant,
    mock_vehicle_data,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests that the update services work."""

    await setup_platform(hass, [Platform.UPDATE])

    entity_id = "update.test_update"

    with patch(
        "homeassistant.components.teslemetry.VehicleSpecific.schedule_software_update",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        call.assert_called_once()

    VEHICLE_INSTALLING = copy.deepcopy(VEHICLE_DATA)
    VEHICLE_INSTALLING["response"]["vehicle_state"]["software_update"]["status"] = (
        INSTALLING
    )
    mock_vehicle_data.return_value = VEHICLE_INSTALLING
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["in_progress"] == 1
