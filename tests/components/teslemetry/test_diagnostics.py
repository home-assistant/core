"""Test the Teslemetry Diagnostics."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.teslemetry.const import DOMAIN
from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import async_fire_time_changed
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
) -> None:
    """Test diagnostics for a polling vehicle."""

    entry = await setup_platform(hass)

    # Wait for coordinator refresh
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == snapshot

    # A polling vehicle's data entities keep the coordinator polling; its
    # stateless command entities (buttons) are in the streaming family instead.
    entities = diag["vehicles"][0]["entities"]
    assert "polling" in set(entities.values())
    assert set(entities.values()) <= {"polling", "streaming"}


async def test_diagnostics_streaming_entities(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test diagnostics reports the data source of a streaming vehicle's entities."""

    entry = await setup_platform(hass)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    entities = diag["vehicles"][0]["entities"]
    assert entities
    assert set(entities.values()) == {"streaming"}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_diagnostics_streaming_and_polling_entities(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test diagnostics reports both sources when a streaming vehicle also polls."""

    entry = await setup_platform(hass)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    entities = diag["vehicles"][0]["entities"]
    assert "streaming" in entities.values()
    assert "polling" in entities.values()
    assert set(entities.values()) <= {"streaming", "polling"}


@pytest.mark.usefixtures("mock_legacy")
async def test_diagnostics_no_entities(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test diagnostics when no entities are enabled."""

    entry = await setup_platform(hass, platforms=[])

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag["vehicles"]
    for vehicle in diag["vehicles"]:
        assert vehicle["entities"] == {}


@pytest.mark.usefixtures("mock_legacy")
async def test_diagnostics_enabled_entity_source(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test diagnostics reports an enabled entity whose platform is not loaded."""

    entry = await setup_platform(hass, platforms=[])
    vehicle = entry.runtime_data.vehicles[0]

    # An enabled entity with no platform loaded is neither a coordinator
    # listener nor a live streaming entity, so it falls back to "enabled".
    registry_entry = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{vehicle.vin}-charge_state_usable_battery_level",
        config_entry=entry,
    )

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    entities = diag["vehicles"][0]["entities"]
    assert entities[registry_entry.entity_id] == "enabled"


async def test_streaming_vehicle_does_not_poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Test a streaming vehicle's coordinator gains no listeners and never polls.

    Streaming entities must not carry a coordinator listener context: giving
    them one would make the vehicle coordinator start polling, which is the
    behaviour this diagnostics change must not introduce.
    """

    entry = await setup_platform(hass)
    coordinator = entry.runtime_data.vehicles[0].coordinator

    # No enabled entity keeps the coordinator polling.
    assert list(coordinator.async_contexts()) == []

    mock_vehicle_data.reset_mock()
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # With no listeners the coordinator never polls, even though its update
    # interval is set for this vehicle.
    mock_vehicle_data.assert_not_called()
