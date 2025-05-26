"""The tests for the Ring light platform."""

from unittest.mock import Mock

import pytest
import ring_doorbell
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import MockConfigEntry, setup_platform

from tests.common import snapshot_platform


async def test_states(
    hass: HomeAssistant,
    mock_ring_client: Mock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states."""
    mock_config_entry.add_to_hass(hass)
    await setup_platform(hass, Platform.LIGHT)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_light_off_reports_correctly(
    hass: HomeAssistant, mock_ring_client
) -> None:
    """Tests that the initial state of a device that should be off is correct."""
    await setup_platform(hass, Platform.LIGHT)

    state = hass.states.get("light.front_light")
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Front Light"


async def test_light_on_reports_correctly(
    hass: HomeAssistant, mock_ring_client
) -> None:
    """Tests that the initial state of a device that should be on is correct."""
    await setup_platform(hass, Platform.LIGHT)

    state = hass.states.get("light.internal_light")
    assert state.state == "on"
    assert state.attributes.get("friendly_name") == "Internal Light"


async def test_light_can_be_turned_on(hass: HomeAssistant, mock_ring_client) -> None:
    """Tests the light turns on correctly."""
    await setup_platform(hass, Platform.LIGHT)

    state = hass.states.get("light.front_light")
    assert state.state == "off"

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.front_light"}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.front_light")
    assert state.state == "on"


@pytest.mark.parametrize(
    ("exception_type", "reauth_expected"),
    [
        (ring_doorbell.AuthenticationError, True),
        (ring_doorbell.RingTimeout, False),
        (ring_doorbell.RingError, False),
    ],
    ids=["Authentication", "Timeout", "Other"],
)
async def test_light_errors_when_turned_on(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
    exception_type,
    reauth_expected,
) -> None:
    """Tests the light turns on correctly."""
    await setup_platform(hass, Platform.LIGHT)
    config_entry = hass.config_entries.async_entries("ring")[0]

    assert not any(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))

    front_light_mock = mock_ring_devices.get_device(765432)
    front_light_mock.async_set_lights.side_effect = exception_type

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "light", "turn_on", {"entity_id": "light.front_light"}, blocking=True
        )
    await hass.async_block_till_done()
    front_light_mock.async_set_lights.assert_called_once()

    assert (
        any(
            flow
            for flow in config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
            if flow["handler"] == "ring"
        )
        == reauth_expected
    )
