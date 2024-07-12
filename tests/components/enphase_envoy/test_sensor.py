"""Test Enphase Envoy sensors."""

from collections.abc import AsyncGenerator
from unittest.mock import Mock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy",
        "envoy_1p_metered",
        "envoy_metered_batt_relay",
        "envoy_nobatt_metered_3p",
        "envoy_tot_cons_metered",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    setup_enphase_envoy: AsyncGenerator[None],
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_envoy: Mock,
) -> None:
    """Test sensor platform entities against snapshot."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
