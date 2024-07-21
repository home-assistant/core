"""The tests for the Ring light platform."""

from unittest.mock import PropertyMock

import pytest
import ring_doorbell

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


async def test_entity_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ring_client,
) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, Platform.LIGHT)

    entry = entity_registry.async_get("light.front_light")
    assert entry.unique_id == "765432"

    entry = entity_registry.async_get("light.internal_light")
    assert entry.unique_id == "345678"


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


async def test_updates_work(
    hass: HomeAssistant, mock_ring_client, mock_ring_devices
) -> None:
    """Tests the update service works correctly."""
    await setup_platform(hass, Platform.LIGHT)
    state = hass.states.get("light.front_light")
    assert state.state == "off"

    front_light_mock = mock_ring_devices.get_device(765432)
    front_light_mock.lights = "on"

    await hass.services.async_call("ring", "update", {}, blocking=True)

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
    p = PropertyMock(side_effect=exception_type)
    type(front_light_mock).lights = p

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "light", "turn_on", {"entity_id": "light.front_light"}, blocking=True
        )
    await hass.async_block_till_done()
    p.assert_called_once()

    assert (
        any(
            flow
            for flow in config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
            if flow["handler"] == "ring"
        )
        == reauth_expected
    )
