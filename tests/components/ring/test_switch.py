"""The tests for the Ring switch platform."""
from datetime import timedelta
import logging
from unittest.mock import PropertyMock, patch

import pytest
from requests import Timeout
import requests_mock

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

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


@pytest.mark.parametrize("switch_type", ["siren", "motion_detection"])
async def test_timeouts(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, caplog, switch_type
) -> None:
    """Test timouts."""
    caplog.set_level(logging.ERROR)
    await setup_platform(hass, Platform.SWITCH)
    hass.states.get("switch.front_" + switch_type)

    with patch(
        "ring_doorbell.stickup_cam.RingStickUpCam." + switch_type,
        new_callable=PropertyMock,
        side_effect=Timeout(),
    ):
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.front_" + switch_type},
            blocking=True,
        )

    assert len(caplog.records) > 0
    assert caplog.records[0].module == "switch"
    assert "Time out setting switch" in caplog.records[0].message


@pytest.mark.parametrize("switch_type", ["siren", "motion_detection"])
async def test_no_updates_until(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, switch_type
) -> None:
    """Tests the update service works correctly."""
    await setup_platform(hass, Platform.SWITCH)
    state = hass.states.get("switch.front_" + switch_type)
    assert state.state == "off"

    await hass.services.async_call("ring", "update", {}, blocking=True)
    await hass.async_block_till_done()

    dtpast = dt_util.utcnow() - timedelta(seconds=10)
    with patch("homeassistant.util.dt.utcnow", return_value=dtpast), patch(
        "ring_doorbell.stickup_cam.RingStickUpCam." + switch_type,
        new_callable=PropertyMock,
    ) as mock:
        await hass.services.async_call("ring", "update", {}, blocking=True)
        assert mock.call_count == 0
