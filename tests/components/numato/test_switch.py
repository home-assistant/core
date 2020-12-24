"""Tests for the numato switch platform."""
from homeassistant.components import switch
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.helpers import discovery
from homeassistant.setup import async_setup_component

from .common import NUMATO_CFG, mockup_raise

MOCKUP_ENTITY_IDS = {
    "switch.numato_switch_mock_port5",
    "switch.numato_switch_mock_port6",
}


async def test_failing_setups_no_entities(hass, numato_fixture, monkeypatch):
    """When port setup fails, no entity shall be created."""
    monkeypatch.setattr(numato_fixture.NumatoDeviceMock, "setup", mockup_raise)
    assert await async_setup_component(hass, "numato", NUMATO_CFG)
    await hass.async_block_till_done()
    for entity_id in MOCKUP_ENTITY_IDS:
        assert entity_id not in hass.states.async_entity_ids()


async def test_regular_hass_operations(hass, numato_fixture):
    """Test regular operations from within Home Assistant."""
    assert await async_setup_component(hass, "numato", NUMATO_CFG)
    await hass.async_block_till_done()  # wait until services are registered
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.numato_switch_mock_port5"},
        blocking=True,
    )
    assert hass.states.get("switch.numato_switch_mock_port5").state == "on"
    assert numato_fixture.devices[0].values[5] == 1
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.numato_switch_mock_port6"},
        blocking=True,
    )
    assert hass.states.get("switch.numato_switch_mock_port6").state == "on"
    assert numato_fixture.devices[0].values[6] == 1
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.numato_switch_mock_port5"},
        blocking=True,
    )
    assert hass.states.get("switch.numato_switch_mock_port5").state == "off"
    assert numato_fixture.devices[0].values[5] == 0
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.numato_switch_mock_port6"},
        blocking=True,
    )
    assert hass.states.get("switch.numato_switch_mock_port6").state == "off"
    assert numato_fixture.devices[0].values[6] == 0


async def test_failing_hass_operations(hass, numato_fixture, monkeypatch):
    """Test failing operations called from within Home Assistant.

    Switches remain in their initial 'off' state when the device can't
    be written to.
    """
    assert await async_setup_component(hass, "numato", NUMATO_CFG)

    await hass.async_block_till_done()  # wait until services are registered
    monkeypatch.setattr(numato_fixture.devices[0], "write", mockup_raise)
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.numato_switch_mock_port5"},
        blocking=True,
    )
    assert hass.states.get("switch.numato_switch_mock_port5").state == "off"
    assert not numato_fixture.devices[0].values[5]
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.numato_switch_mock_port6"},
        blocking=True,
    )
    assert hass.states.get("switch.numato_switch_mock_port6").state == "off"
    assert not numato_fixture.devices[0].values[6]
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.numato_switch_mock_port5"},
        blocking=True,
    )
    assert hass.states.get("switch.numato_switch_mock_port5").state == "off"
    assert not numato_fixture.devices[0].values[5]
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.numato_switch_mock_port6"},
        blocking=True,
    )
    assert hass.states.get("switch.numato_switch_mock_port6").state == "off"
    assert not numato_fixture.devices[0].values[6]


async def test_switch_setup_without_discovery_info(hass, config, numato_fixture):
    """Test handling of empty discovery_info."""
    numato_fixture.discover()
    await discovery.async_load_platform(hass, "switch", "numato", None, config)
    for entity_id in MOCKUP_ENTITY_IDS:
        assert entity_id not in hass.states.async_entity_ids()
    await hass.async_block_till_done()  # wait for numato platform to be loaded
    for entity_id in MOCKUP_ENTITY_IDS:
        assert entity_id in hass.states.async_entity_ids()
