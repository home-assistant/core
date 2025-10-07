"""iNELS switch platform testing."""

from unittest.mock import patch

import pytest

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .common import MAC_ADDRESS, UNIQUE_ID, get_entity_id

DT_07 = "07"
DT_100 = "100"
DT_BITS = "bits"


@pytest.fixture(params=["simple_relay", "relay", "bit"])
def entity_config(request: pytest.FixtureRequest):
    """Fixture to provide parameterized entity configuration for switch tests."""
    configs = {
        "simple_relay": {
            "entity_type": "switch",
            "device_type": "simple_relay",
            "dev_type": DT_07,
            "unique_id": UNIQUE_ID,
            "gw_connected_topic": f"inels/connected/{MAC_ADDRESS}/gw",
            "connected_topic": f"inels/connected/{MAC_ADDRESS}/{DT_07}/{UNIQUE_ID}",
            "status_topic": f"inels/status/{MAC_ADDRESS}/{DT_07}/{UNIQUE_ID}",
            "base_topic": f"{MAC_ADDRESS}/{DT_07}/{UNIQUE_ID}",
            "switch_on_value": "07\n01\n92\n09\n",
            "switch_off_value": "07\n00\n92\n09\n",
        },
        "relay": {
            "entity_type": "switch",
            "device_type": "relay",
            "dev_type": DT_100,
            "unique_id": UNIQUE_ID,
            "gw_connected_topic": f"inels/connected/{MAC_ADDRESS}/gw",
            "connected_topic": f"inels/connected/{MAC_ADDRESS}/{DT_100}/{UNIQUE_ID}",
            "status_topic": f"inels/status/{MAC_ADDRESS}/{DT_100}/{UNIQUE_ID}",
            "base_topic": f"{MAC_ADDRESS}/{DT_100}/{UNIQUE_ID}",
            "switch_on_value": "07\n00\n0A\n28\n00\n",
            "switch_off_value": "06\n00\n0A\n28\n00\n",
            "alerts": {
                "overflow": "06\n00\n0A\n28\n01\n",
            },
        },
        "bit": {
            "entity_type": "switch",
            "device_type": "bit",
            "dev_type": DT_BITS,
            "unique_id": UNIQUE_ID,
            "gw_connected_topic": f"inels/connected/{MAC_ADDRESS}/gw",
            "connected_topic": f"inels/connected/{MAC_ADDRESS}/{DT_BITS}/{UNIQUE_ID}",
            "status_topic": f"inels/status/{MAC_ADDRESS}/{DT_BITS}/{UNIQUE_ID}",
            "base_topic": f"{MAC_ADDRESS}/{DT_BITS}/{UNIQUE_ID}",
            "switch_on_value": b'{"state":{"000":1,"001":1}}',
            "switch_off_value": b'{"state":{"000":0,"001":0}}',
        },
    }
    return configs[request.param]


@pytest.mark.parametrize(
    "entity_config", ["simple_relay", "relay", "bit"], indirect=True
)
@pytest.mark.parametrize(
    ("gw_available", "device_available", "expected_state"),
    [
        (True, False, STATE_UNAVAILABLE),
        (False, True, STATE_UNAVAILABLE),
        (True, True, STATE_ON),
    ],
)
async def test_switch_availability(
    hass: HomeAssistant,
    setup_entity,
    entity_config,
    gw_available,
    device_available,
    expected_state,
) -> None:
    """Test switch availability and state under different gateway and device availability conditions."""

    switch = await setup_entity(
        entity_config,
        status_value=entity_config["switch_on_value"],
        gw_available=gw_available,
        device_available=device_available,
        index=0 if entity_config["device_type"] == "bit" else None,
    )

    assert switch is not None
    assert switch.state == expected_state


@pytest.mark.parametrize(
    ("entity_config", "index"),
    [
        ("simple_relay", None),
        ("relay", None),
        ("bit", 0),
    ],
    indirect=["entity_config"],
)
async def test_switch_turn_on(
    hass: HomeAssistant, setup_entity, entity_config, index
) -> None:
    """Test turning on a switch."""
    switch = await setup_entity(
        entity_config, status_value=entity_config["switch_off_value"], index=index
    )

    assert switch is not None
    assert switch.state == STATE_OFF

    with patch("inelsmqtt.devices.Device.set_ha_value") as mock_set_state:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: get_entity_id(entity_config, index)},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

        ha_value = mock_set_state.call_args.args[0]
        assert getattr(ha_value, entity_config["device_type"])[0].is_on is True


@pytest.mark.parametrize(
    ("entity_config", "index"),
    [
        ("simple_relay", None),
        ("relay", None),
        ("bit", 0),
    ],
    indirect=["entity_config"],
)
async def test_switch_turn_off(
    hass: HomeAssistant, setup_entity, entity_config, index
) -> None:
    """Test turning off a switch."""
    switch = await setup_entity(
        entity_config, status_value=entity_config["switch_on_value"], index=index
    )

    assert switch is not None
    assert switch.state == STATE_ON

    with patch("inelsmqtt.devices.Device.set_ha_value") as mock_set_state:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: get_entity_id(entity_config, index)},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

        ha_value = mock_set_state.call_args.args[0]
        assert getattr(ha_value, entity_config["device_type"])[0].is_on is False
