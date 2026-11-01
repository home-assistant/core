"""Tests for the Geniushub switch platform."""

from unittest.mock import ANY, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.geniushub.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_geniushub_cloud")
async def test_cloud_all_sensors(
    hass: HomeAssistant,
    mock_cloud_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation of the Genius Hub switch entities."""
    with patch("homeassistant.components.geniushub.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_cloud_config_entry)

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_cloud_config_entry.entry_id
    )


@pytest.mark.usefixtures("mock_geniushub_cloud")
@pytest.mark.parametrize(
    ("domain", "service", "service_data", "expected_duration"),
    [
        pytest.param(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {}, 3600, id="turn_on_default_duration"
        ),
        pytest.param(
            DOMAIN,
            "set_switch_override",
            {"duration": 36000},
            36000,
            id="set_switch_override_duration",
        ),
    ],
)
async def test_turn_on_override_duration(
    hass: HomeAssistant,
    mock_cloud_config_entry: MockConfigEntry,
    domain: str,
    service: str,
    service_data: dict[str, int],
    expected_duration: int,
) -> None:
    """Test turning on a switch zone overrides it for a duration in seconds."""
    with patch("homeassistant.components.geniushub.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_cloud_config_entry)

    with patch(
        "geniushubclient.zone.GeniusZone.set_override", autospec=True
    ) as mock_set_override:
        await hass.services.async_call(
            domain,
            service,
            {ATTR_ENTITY_ID: "switch.bedroom_socket", **service_data},
            blocking=True,
        )

    mock_set_override.assert_awaited_once_with(ANY, 1, expected_duration)
