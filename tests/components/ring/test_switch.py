"""The tests for the Ring switch platform."""
import pytest
import requests_mock

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

from tests.common import load_fixture


@pytest.mark.parametrize("switch_type", ["siren", "motion_detection"])
async def test_entity_registry(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, switch_type
) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, Platform.SWITCH)
    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("switch.front_" + switch_type)
    assert entry.unique_id == "765432-" + switch_type

    entry = entity_registry.async_get("switch.internal_" + switch_type)
    assert entry.unique_id == "345678-" + switch_type


@pytest.mark.parametrize(
    ("switch_type", "friendly_name"),
    [
        ("siren", "Front Siren"),
        ("motion_detection", "Front Motion Detection"),
    ],
    ids=("siren", "motion_detection"),
)
async def test_switch_off_reports_correctly(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, switch_type, friendly_name
) -> None:
    """Tests that the initial state of a device that should be off is correct."""
    await setup_platform(hass, Platform.SWITCH)

    state = hass.states.get("switch.front_" + switch_type)
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == friendly_name


@pytest.mark.parametrize(
    ("switch_type", "friendly_name", "icon_name"),
    [
        ("siren", "Internal Siren", "mdi:alarm-bell"),
        ("motion_detection", "Internal Motion Detection", "mdi:motion-sensor"),
    ],
    ids=("siren", "motion_detection"),
)
async def test_switch_on_reports_correctly(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    switch_type,
    friendly_name,
    icon_name,
) -> None:
    """Tests that the initial state of a device that should be on is correct."""
    await setup_platform(hass, Platform.SWITCH)

    state = hass.states.get("switch.internal_" + switch_type)
    assert state.state == "on"
    assert state.attributes.get("friendly_name") == friendly_name
    assert state.attributes.get("icon") == icon_name


@pytest.mark.parametrize("switch_type", ["siren", "motion_detection"])
async def test_switch_can_be_turned_on(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, switch_type
) -> None:
    """Tests the siren turns on correctly."""
    await setup_platform(hass, Platform.SWITCH)

    # Mocks the response for turning a siren on
    requests_mock.put(
        "https://api.ring.com/clients_api/doorbots/765432/siren_on",
        text=load_fixture("doorbot_siren_on_response.json", "ring"),
    )

    state = hass.states.get("switch.front_" + switch_type)
    assert state.state == "off"

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.front_" + switch_type}, blocking=True
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.front_" + switch_type)
    assert state.state == "on"


@pytest.mark.parametrize("switch_type", ["siren", "motion_detection"])
async def test_updates_work(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, switch_type
) -> None:
    """Tests the update service works correctly."""
    await setup_platform(hass, Platform.SWITCH)
    state = hass.states.get("switch.front_" + switch_type)
    assert state.state == "off"
    # Changes the return to indicate that the switch is now on.
    requests_mock.get(
        "https://api.ring.com/clients_api/ring_devices",
        text=load_fixture("devices_updated.json", "ring"),
    )

    await hass.services.async_call("ring", "update", {}, blocking=True)

    await hass.async_block_till_done()

    state = hass.states.get("switch.front_" + switch_type)
    assert state.state == "on"
