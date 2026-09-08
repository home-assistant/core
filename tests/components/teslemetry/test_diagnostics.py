"""Test the Teslemetry Diagnostics."""

from copy import deepcopy
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
from .const import METADATA, METADATA_LEGACY, PRODUCTS

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


async def test_diagnostics_streaming_and_polling_vehicles(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_products: AsyncMock,
    mock_metadata: AsyncMock,
) -> None:
    """Test diagnostics attributes each vehicle's entities to its own source.

    A vehicle either streams or polls, never both, so the two sources only
    appear together across different vehicles. This sets up one polling and
    one streaming vehicle and asserts diagnostics reports the polling
    vehicle's data entities as "polling" and the streaming vehicle's entities
    as "streaming", without cross-attributing one vehicle's source to the
    other.
    """
    poll_vin = "LRW3F7EK4NC700000"
    stream_vin = "LRW3F7EK4NC700001"

    products = deepcopy(PRODUCTS)
    poll_product = next(p for p in products["response"] if p.get("vin") == poll_vin)
    poll_product["display_name"] = "Poll"
    stream_product = deepcopy(poll_product)
    stream_product["vin"] = stream_vin
    stream_product["display_name"] = "Stream"
    products["response"].append(stream_product)
    mock_products.return_value = products

    metadata = deepcopy(METADATA)
    metadata["vehicles"] = {
        poll_vin: deepcopy(METADATA_LEGACY["vehicles"][poll_vin]),
        stream_vin: deepcopy(METADATA["vehicles"][poll_vin]),
    }
    mock_metadata.return_value = metadata

    entry = await setup_platform(hass)

    vehicles = {vehicle.vin: vehicle for vehicle in entry.runtime_data.vehicles}
    assert vehicles[poll_vin].poll is True
    assert vehicles[stream_vin].poll is False

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    def sources_for(object_id_prefix: str) -> set[str]:
        """Return the sources of the vehicle whose entity_ids use the prefix."""
        return next(
            set(vehicle["entities"].values())
            for vehicle in diag["vehicles"]
            if all(
                entity_id.split(".", 1)[1].startswith(object_id_prefix)
                for entity_id in vehicle["entities"]
            )
        )

    poll_sources = sources_for("poll_")
    stream_sources = sources_for("stream_")

    # The polling vehicle's data entities keep its coordinator polling...
    assert "polling" in poll_sources
    # ...while the streaming vehicle reports only "streaming", so neither
    # vehicle's source leaks into the other's diagnostics.
    assert stream_sources == {"streaming"}
    # No entity falls back to "enabled": every one maps to a live source.
    assert poll_sources <= {"polling", "streaming"}


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
