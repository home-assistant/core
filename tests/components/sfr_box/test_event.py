"""Test the SFR Box events."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

# from homeassistant.components.event import DOMAIN as EVENT_DOMAIN, SERVICE_PRESS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import snapshot_platform

pytestmark = pytest.mark.usefixtures(
    "system_get_info",
    "dsl_get_info",
    "voip_get_info",
    "voip_get_call_history_list",
    "wan_get_info",
)


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS_WITH_AUTH."""
    with (
        patch("homeassistant.components.sfr_box.PLATFORMS_WITH_AUTH", [Platform.EVENT]),
        patch("homeassistant.components.sfr_box.coordinator.SFRBox.authenticate"),
    ):
        yield


async def test_events(
    hass: HomeAssistant,
    config_entry_with_auth: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for SFR Box events."""
    await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, config_entry_with_auth.entry_id
    )
