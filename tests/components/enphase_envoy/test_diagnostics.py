"""Test Enphase Envoy diagnostics."""

from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import PLATFORMS as ENVOY_PLATFORMS
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.components.enphase_envoy import setup_with_selected_platforms
from tests.typing import ClientSessionGenerator

# Fields to exclude from snapshot as they change each run
TO_EXCLUDE = {
    "id",
    "device_id",
    "via_device_id",
    "last_updated",
    "last_changed",
    "last_reported",
}

# fixture files to test
ALL_FIXTURES = (
    [
        pytest.param("envoy", id="envoy"),
        pytest.param("envoy_metered_batt_relay", id="envoy_metered_batt_relay"),
        pytest.param("envoy_nobatt_metered_3p", id="envoy_nobatt_metered_3p"),
        pytest.param("envoy_1p_metered", id="envoy_1p_metered"),
        pytest.param("envoy_tot_cons_metered", id="envoy_tot_cons_metered"),
    ],
)


def limit_diagnostic_attrs(prop, path) -> bool:
    """Mark attributes to exclude from diagnostic snapshot."""
    return prop in TO_EXCLUDE


@pytest.mark.parametrize(("mock_envoy"), *ALL_FIXTURES, indirect=["mock_envoy"])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    hass_client: ClientSessionGenerator,
    mock_envoy: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await setup_with_selected_platforms(hass, config_entry, ENVOY_PLATFORMS)
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics

    # do not use snapshot compare on overall diagnostics as snapshot file content order varies
    # test the individual items of the diagnostics report to avoid false snapshot compare assertions
    assert diagnostics["config_entry"] == snapshot(
        name="config_entry", exclude=limit_diagnostic_attrs
    )
    assert diagnostics["envoy_properties"] == snapshot(
        name="envoy_properties", exclude=limit_diagnostic_attrs
    )
    assert diagnostics["raw_data"] == snapshot(
        name="raw_data", exclude=limit_diagnostic_attrs
    )
    assert diagnostics["envoy_model_data"] == snapshot(
        name="envoy_model_data", exclude=limit_diagnostic_attrs
    )

    for devices in diagnostics["envoy_entities_by_device"]:
        for entity in devices["entities"]:
            assert entity["entity"] == snapshot(
                name=f"{entity["entity"]["entity_id"]}-entry",
                exclude=limit_diagnostic_attrs,
            )
            assert entity["state"] == snapshot(
                name=f"{entity["entity"]["entity_id"]}-state",
                exclude=limit_diagnostic_attrs,
            )
