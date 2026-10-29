"""Tests for the numato switch platform."""

import pytest

from homeassistant.components import switch
from homeassistant.components.numato import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import discovery
from homeassistant.setup import async_setup_component

from .common import NUMATO_CFG, mockup_raise

MOCKUP_ENTITY_IDS = {
    "switch.numato_switch_mock_port5",
    "switch.numato_switch_mock_port6",
}


async def test_failing_setups_no_entities(
    hass: HomeAssistant, numato_fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When port setup fails, no entity shall be created."""
    monkeypatch.setattr(numato_fixture.NumatoDeviceMock, "setup", mockup_raise)
    assert await async_setup_component(hass, DOMAIN, NUMATO_CFG)
    await hass.async_block_till_done()
    for entity_id in MOCKUP_ENTITY_IDS:
        assert entity_id not in hass.states.async_entity_ids()


async def test_regular_hass_operations(hass: HomeAssistant, numato_fixture) -> None:
    """Test regular operations from within Home Assistant."""
    assert await async_setup_component(hass, DOMAIN, NUMATO_CFG)
    await hass.async_block_till_done()  # wait until services are registered
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.numato_switch_mock_port5"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.numato_switch_mock_port5").state == "on"
    assert numato_fixture.devices[0].values[5] == 1
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.numato_switch_mock_port6"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.numato_switch_mock_port6").state == "on"
    assert numato_fixture.devices[0].values[6] == 1
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.numato_switch_mock_port5"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.numato_switch_mock_port5").state == "off"
    assert numato_fixture.devices[0].values[5] == 0
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.numato_switch_mock_port6"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.numato_switch_mock_port6").state == "off"
    assert numato_fixture.devices[0].values[6] == 0


@pytest.mark.parametrize(
    ("service", "entity_id", "port", "translation_key"),
    [
        pytest.param(
            SERVICE_TURN_ON,
            "switch.numato_switch_mock_port5",
            5,
            "turn_on_failed",
            id="turn_on_port5",
        ),
        pytest.param(
            SERVICE_TURN_ON,
            "switch.numato_switch_mock_port6",
            6,
            "turn_on_failed",
            id="turn_on_port6",
        ),
        pytest.param(
            SERVICE_TURN_OFF,
            "switch.numato_switch_mock_port5",
            5,
            "turn_off_failed",
            id="turn_off_port5",
        ),
        pytest.param(
            SERVICE_TURN_OFF,
            "switch.numato_switch_mock_port6",
            6,
            "turn_off_failed",
            id="turn_off_port6",
        ),
    ],
)
async def test_failing_hass_operations(
    hass: HomeAssistant,
    numato_fixture,
    monkeypatch: pytest.MonkeyPatch,
    service: str,
    entity_id: str,
    port: int,
    translation_key: str,
) -> None:
    """Test failing operations called from within Home Assistant.

    Switches remain in their initial 'off' state when the device can't
    be written to.
    """
    assert await async_setup_component(hass, DOMAIN, NUMATO_CFG)

    await hass.async_block_till_done()  # wait until services are registered
    monkeypatch.setattr(numato_fixture.devices[0], "write", mockup_raise)
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            switch.DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    assert exc_info.value.translation_key == translation_key
    assert hass.states.get(entity_id).state == "off"
    assert not numato_fixture.devices[0].values[port]


async def test_switch_setup_without_discovery_info(
    hass: HomeAssistant, config, numato_fixture
) -> None:
    """Test handling of empty discovery_info."""
    numato_fixture.discover()
    await discovery.async_load_platform(hass, Platform.SWITCH, "numato", None, config)
    for entity_id in MOCKUP_ENTITY_IDS:
        assert entity_id not in hass.states.async_entity_ids()
    await hass.async_block_till_done()  # wait for numato platform to be loaded
    for entity_id in MOCKUP_ENTITY_IDS:
        assert entity_id in hass.states.async_entity_ids()
