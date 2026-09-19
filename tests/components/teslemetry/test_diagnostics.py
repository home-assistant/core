"""Test the Teslemetry Diagnostics."""

from copy import deepcopy
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.teslemetry.const import DOMAIN
from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.components.teslemetry.diagnostics import (
    SOURCE_ENABLED,
    SOURCE_POLLING,
    SOURCE_STREAMING,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.json import JsonObjectType

from . import reload_platform, setup_platform
from .const import METADATA, METADATA_LEGACY, PRODUCTS, PRODUCTS_MODERN

from tests.common import async_fire_time_changed
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

VEHICLE_VIN = "LRW3F7EK4NC700000"
STREAM_VIN = "LRW3F7EK4NC700001"
# vehicle_state.vehicle_name in the vehicle data fixture, which replaces the
# product data once a vehicle polls.
POLLED_NAME = "Test"
STREAM_NAME = "Stream"


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
    sources = set(diag["vehicles"][0]["entities"].values())
    assert SOURCE_POLLING in sources
    assert sources <= {SOURCE_POLLING, SOURCE_STREAMING}


async def test_diagnostics_streaming_vehicle(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Test a streaming vehicle reports only streaming entities and never polls.

    Streaming entities must not carry a coordinator listener context: giving
    them one would make the vehicle coordinator start polling, which is the
    behaviour this diagnostics change must not introduce.
    """

    entry = await setup_platform(hass)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    entities = diag["vehicles"][0]["entities"]
    assert entities
    assert set(entities.values()) == {SOURCE_STREAMING}

    mock_vehicle_data.reset_mock()
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Nothing listens to the coordinator, so it never polls even though its
    # update interval is set for this vehicle.
    mock_vehicle_data.assert_not_called()


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
    vehicle's data entities as polling and the streaming vehicle's entities
    as streaming, without cross-attributing one vehicle's source to the other.
    """
    products = deepcopy(PRODUCTS)
    poll_product = next(p for p in products["response"] if p.get("vin") == VEHICLE_VIN)
    stream_product = deepcopy(poll_product)
    stream_product["vin"] = STREAM_VIN
    stream_product["display_name"] = STREAM_NAME
    products["response"].append(stream_product)
    mock_products.return_value = products

    metadata = deepcopy(METADATA)
    metadata["vehicles"] = {
        VEHICLE_VIN: deepcopy(METADATA_LEGACY["vehicles"][VEHICLE_VIN]),
        STREAM_VIN: deepcopy(METADATA["vehicles"][VEHICLE_VIN]),
    }
    mock_metadata.return_value = metadata

    entry = await setup_platform(hass)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    # A vehicle that polls replaces its product data with its polled response,
    # which carries the name under vehicle_state; one that only streams never
    # refreshes, so the product's display name survives.
    sources = {
        vehicle["data"].get("display_name")
        or vehicle["data"]["vehicle_state_vehicle_name"]: set(
            vehicle["entities"].values()
        )
        for vehicle in diag["vehicles"]
    }

    # The polling vehicle's data entities keep its coordinator polling...
    assert SOURCE_POLLING in sources[POLLED_NAME]
    # ...while the streaming vehicle reports only streaming, so neither
    # vehicle's source leaks into the other's diagnostics.
    assert sources[STREAM_NAME] == {SOURCE_STREAMING}
    # No entity falls back to enabled: every one maps to a live source.
    assert sources[POLLED_NAME] <= {SOURCE_POLLING, SOURCE_STREAMING}


@pytest.mark.parametrize(
    ("products", "pref_disable_polling"),
    [
        pytest.param(PRODUCTS_MODERN, False, id="no_update_interval"),
        pytest.param(PRODUCTS, True, id="polling_disabled"),
    ],
)
@pytest.mark.usefixtures("mock_legacy")
async def test_diagnostics_listener_that_cannot_poll(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_products: AsyncMock,
    mock_vehicle_data: AsyncMock,
    products: JsonObjectType,
    pref_disable_polling: bool,
) -> None:
    """Test a coordinator listener is not reported as polling when nothing polls.

    A vehicle without an update interval, or one whose config entry has
    polling disabled, is never scheduled to refresh, so its listeners cost no
    credits and must not be blamed for the vehicle's usage.
    """
    mock_products.return_value = products
    entry = await setup_platform(hass)
    hass.config_entries.async_update_entry(
        entry, pref_disable_polling=pref_disable_polling
    )
    await reload_platform(hass, entry)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    sources = set(diag["vehicles"][0]["entities"].values())
    assert SOURCE_ENABLED in sources
    assert SOURCE_POLLING not in sources

    mock_vehicle_data.reset_mock()
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # The label matches reality: no refresh is scheduled for this vehicle.
    mock_vehicle_data.assert_not_called()


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

    # An enabled entity with no platform loaded is neither a coordinator
    # listener nor a live streaming entity, so it falls back to enabled.
    registry_entry = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{VEHICLE_VIN}-charge_state_usable_battery_level",
        config_entry=entry,
    )

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    entities = diag["vehicles"][0]["entities"]
    assert entities[registry_entry.entity_id] == SOURCE_ENABLED
