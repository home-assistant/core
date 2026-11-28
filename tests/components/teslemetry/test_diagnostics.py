"""Test the Teslemetry Diagnostics."""

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.teslemetry.const import (
    CONF_VIN,
    DOMAIN,
    SUBENTRY_TYPE_VEHICLE,
)
from homeassistant.components.teslemetry.diagnostics import (
    SOURCE_COMMAND,
    SOURCE_ENABLED,
    SOURCE_STREAMING,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import mock_config_entry, setup_platform
from .const import METADATA, METADATA_LEGACY, PRODUCTS

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
    mock_legacy: AsyncMock,
    mock_energy_totals_stream: MagicMock,
) -> None:
    """Test diagnostics for a polling vehicle."""

    entry = await setup_platform(hass)

    mock_energy_totals_stream.send()
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == snapshot


async def test_diagnostics_streaming_vehicle(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a streaming vehicle reports only streaming and command entities."""

    entry = await setup_platform(hass)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    entities = diag["vehicles"][0]["entities"]
    assert entities
    assert set(entities.values()) == {SOURCE_STREAMING, SOURCE_COMMAND}


async def test_diagnostics_streaming_and_polling_vehicles(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_products: AsyncMock,
    mock_metadata: AsyncMock,
) -> None:
    """Test diagnostics attributes each vehicle's entities to its own source.

    A vehicle either polls for its data or streams it, never both, so the
    polling vehicle's data entities are reported as enabled while the
    streaming vehicle's are reported as streaming, with neither vehicle's
    source leaking into the other's diagnostics.
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

    assert len(sources) == 2
    assert sources[POLLED_NAME] == {SOURCE_ENABLED, SOURCE_COMMAND}
    assert sources[STREAM_NAME] == {SOURCE_STREAMING, SOURCE_COMMAND}


@pytest.mark.parametrize(
    ("platforms", "expected_sources"),
    [
        pytest.param([Platform.BUTTON], {SOURCE_COMMAND}, id="command_only"),
        pytest.param([], set(), id="no_entities"),
    ],
)
@pytest.mark.usefixtures("mock_legacy")
async def test_diagnostics_entity_sources(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    platforms: list[Platform],
    expected_sources: set[str],
) -> None:
    """Test the sources reported for the entities a vehicle actually has.

    Buttons subscribe to neither the vehicle coordinator nor a streaming
    field, so even on a polling vehicle they have no state to attribute to
    either source, and a vehicle with no platforms loaded reports nothing.
    """

    entry = await setup_platform(hass, platforms)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert set(diag["vehicles"][0]["entities"].values()) == expected_sources


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


VIN = "LRW3F7EK4NC700000"
ADDRESS = "AA:BB:CC:DD:EE:FF"


def _entry_with_ble() -> MockConfigEntry:
    """Return a config entry whose vehicle subentry is Bluetooth paired."""
    entry = mock_config_entry()
    return MockConfigEntry(
        domain=entry.domain,
        version=entry.version,
        minor_version=entry.minor_version,
        unique_id=entry.unique_id,
        data=dict(entry.data),
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_VEHICLE,
                unique_id=VIN,
                title="Test",
                data={CONF_VIN: VIN, CONF_ADDRESS: ADDRESS},
            )
        ],
    )


@pytest.mark.parametrize(
    ("ble_device", "key_error"),
    [
        pytest.param(MagicMock(), None, id="in_range"),
        pytest.param(None, None, id="out_of_range"),
        pytest.param(MagicMock(), OSError("disk gone"), id="key_load_failed"),
    ],
)
async def test_diagnostics_bluetooth(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    ble_device: MagicMock | None,
    key_error: Exception | None,
) -> None:
    """Test the Bluetooth diagnostics of a paired vehicle."""
    entry = _entry_with_ble()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        mock_parent.return_value.get_private_key = AsyncMock(side_effect=key_error)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diag["vehicles"][0]["bluetooth"] == snapshot
