"""Test Enphase Envoy diagnostics."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pyenphase.exceptions import EnvoyError
from pyenphase.models.meters import CtType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import (
    DOMAIN,
    OPTION_DIAGNOSTICS_INCLUDE_FIXTURES,
)
from homeassistant.components.enphase_envoy.coordinator import MAC_VERIFICATION_DELAY
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

# Fields to exclude from snapshot as they change each run
TO_EXCLUDE = {
    "id",
    "device_id",
    "via_device_id",
    "last_updated",
    "last_changed",
    "last_reported",
    "created_at",
    "modified_at",
}


def limit_diagnostic_attrs(prop, path) -> bool:
    """Mark attributes to exclude from diagnostic snapshot."""
    return prop in TO_EXCLUDE


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    mock_envoy: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await setup_integration(hass, config_entry)
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    ) == snapshot(exclude=limit_diagnostic_attrs)


@pytest.fixture(name="config_entry_options")
def config_entry_options_fixture(hass: HomeAssistant, config: dict[str, str]):
    """Define a config entry fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="45a36e55aaddb2007c5f6602e0c38e72",
        title="Envoy 1234",
        unique_id="1234",
        data=config,
        options={OPTION_DIAGNOSTICS_INCLUDE_FIXTURES: True},
    )


async def test_entry_diagnostics_with_fixtures(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry_options: MockConfigEntry,
    mock_envoy: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await setup_integration(hass, config_entry_options)
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry_options
    ) == snapshot(exclude=limit_diagnostic_attrs)


async def test_entry_diagnostics_with_fixtures_with_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry_options: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
) -> None:
    """Test config entry diagnostics."""
    await setup_integration(hass, config_entry_options)
    mock_envoy.request.side_effect = EnvoyError("Test")
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry_options
    ) == snapshot(exclude=limit_diagnostic_attrs)


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
        "envoy",
    ],
    indirect=["mock_envoy"],
)
async def test_entry_diagnostics_with_interface_information(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test config entry diagnostics including interface data."""
    await setup_integration(hass, config_entry)

    # move time forward so interface information is collected
    freezer.tick(MAC_VERIFICATION_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # fix order of entities by device to avoid snapshot assertion
    # failures due to changed id based order between test runs
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    diagnostics["envoy_entities_by_device"] = [
        {
            "device": device_entities["device"],
            "entities": sorted(
                device_entities["entities"], key=lambda e: e["entity"]["entity_id"]
            ),
        }
        for device_entities in sorted(
            diagnostics["envoy_entities_by_device"],
            key=lambda e: e["device"]["identifiers"],
        )
    ]
    assert diagnostics == snapshot(exclude=limit_diagnostic_attrs)


@pytest.mark.parametrize(
    ("mock_envoy", "ctpresent"),
    [
        ("envoy", ()),
        ("envoy_1p_metered", (CtType.PRODUCTION, CtType.NET_CONSUMPTION)),
        ("envoy_acb_batt", (CtType.PRODUCTION, CtType.NET_CONSUMPTION)),
        ("envoy_eu_batt", (CtType.PRODUCTION, CtType.NET_CONSUMPTION)),
        (
            "envoy_metered_batt_relay",
            (
                CtType.PRODUCTION,
                CtType.NET_CONSUMPTION,
                CtType.STORAGE,
                CtType.BACKFEED,
                CtType.LOAD,
                CtType.EVSE,
                CtType.PV3P,
            ),
        ),
        ("envoy_nobatt_metered_3p", (CtType.PRODUCTION, CtType.NET_CONSUMPTION)),
        ("envoy_tot_cons_metered", (CtType.PRODUCTION, CtType.TOTAL_CONSUMPTION)),
    ],
    indirect=["mock_envoy"],
)
async def test_entry_diagnostics_ct_presence(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    ctpresent: tuple[CtType, ...],
) -> None:
    """Test config entry diagnostics including interface data."""
    await setup_integration(hass, config_entry)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    # are expected ct in diagnostic report
    for ct in ctpresent:
        assert diagnostics["envoy_model_data"]["ctmeters"][ct]

    # are no more ct in diagnostic report as in ctpresent
    for ct in diagnostics["envoy_model_data"]["ctmeters"]:
        assert ct in ctpresent
