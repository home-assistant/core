"""Test the Tesla Fleet update platform."""

import copy
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.tesla_fleet.coordinator import VEHICLE_INTERVAL
from homeassistant.components.tesla_fleet.update import INSTALLING
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA, VEHICLE_DATA_ALT

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_update(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the update entities are correct."""

    await setup_platform(hass, normal_config_entry, [Platform.UPDATE])
    assert_entities(hass, normal_config_entry.entry_id, entity_registry, snapshot)


async def test_update_alt(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Tests that the update entities are correct."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    await setup_platform(hass, normal_config_entry, [Platform.UPDATE])
    assert_entities(hass, normal_config_entry.entry_id, entity_registry, snapshot)


async def test_update_services(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests that the update services work."""

    await setup_platform(hass, normal_config_entry, [Platform.UPDATE])

    entity_id = "update.test_update"

    with patch(
        "tesla_fleet_api.tesla.VehicleFleet.schedule_software_update",
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
    VEHICLE_INSTALLING["response"]["vehicle_state"]["software_update"]["status"] = (  # type: ignore[index]
        INSTALLING
    )
    mock_vehicle_data.return_value = VEHICLE_INSTALLING
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["in_progress"] is True  # type: ignore[union-attr]
