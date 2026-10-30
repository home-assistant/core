"""Test the SFR Box binary sensors."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed, snapshot_platform
from sfrbox_api.exceptions import SFRBoxApiError, SFRBoxAuthenticationError, SFRBoxError
from sfrbox_api.models import SystemInfo
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

WAN_STATUS_ENTITY_ID = "binary_sensor.sfr_box_wan_status"

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


@pytest.mark.parametrize(
    ("side_effect", "flow_sources"),
    [
        pytest.param(SFRBoxAuthenticationError, [SOURCE_REAUTH], id="auth_error"),
        pytest.param(SFRBoxApiError, [], id="api_error"),
        pytest.param(SFRBoxError, [], id="error"),
    ],
)
async def test_update_failure(
    hass: HomeAssistant,
    config_entry_with_auth: ConfigEntry,
    freezer: FrozenDateTimeFactory,
    side_effect: type[Exception],
    flow_sources: list[str],
) -> None:
    """Test polling failures, with reauthentication on invalid credentials."""
    await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(WAN_STATUS_ENTITY_ID).state == STATE_ON

    with patch(
        "homeassistant.components.sfr_box.coordinator.SFRBox.wan_get_info",
        side_effect=side_effect,
    ):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get(WAN_STATUS_ENTITY_ID).state == STATE_UNAVAILABLE
    assert [
        flow["context"]["source"] for flow in hass.config_entries.flow.async_progress()
    ] == flow_sources
