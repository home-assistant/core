"""Test the SFR Box binary sensors."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from sfrbox_api.exceptions import SFRBoxAuthenticationError
from sfrbox_api.models import SystemInfo
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import async_fire_time_changed, snapshot_platform

pytestmark = pytest.mark.usefixtures(
    "system_get_info", "dsl_get_info", "ftth_get_info", "voip_get_info", "wan_get_info"
)


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with (
        patch("homeassistant.components.sfr_box.PLATFORMS", [Platform.BINARY_SENSOR]),
        patch("homeassistant.components.sfr_box.coordinator.SFRBox.authenticate"),
    ):
        yield


@pytest.mark.parametrize("net_infra", ["adsl", "ftth"])
async def test_binary_sensors(
    hass: HomeAssistant,
    config_entry_with_auth: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    system_get_info: SystemInfo,
    net_infra: str,
) -> None:
    """Test for SFR Box binary sensors."""
    system_get_info.net_infra = net_infra
    await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, config_entry_with_auth.entry_id
    )


async def test_binary_sensors_no_auth(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for SFR Box binary sensors."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure auth-only entities are not registered
    assert sorted(entity_registry.entities) == snapshot


async def test_update_invalid_auth(
    hass: HomeAssistant,
    config_entry_with_auth: ConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test reauthentication is started when credentials fail during polling."""
    await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.sfr_box.coordinator.SFRBox.wan_get_info",
        side_effect=SFRBoxAuthenticationError,
    ):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == config_entry_with_auth.entry_id
