"""Test Konnected switch object."""
from unittest.mock import patch

from homeassistant.components import konnected
from homeassistant.components.konnected import async_setup_entry, config_flow
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_on_off(hass):
    """Test turning the light on."""

    device_config = config_flow.CONFIG_ENTRY_SCHEMA(
        {
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "model": "Konnected Pro",
            "access_token": "abcdefgh",
            "api_host": "http://192.168.86.32:8123",
            "default_options": config_flow.OPTIONS_SCHEMA({config_flow.CONF_IO: {}}),
        }
    )

    device_options = config_flow.OPTIONS_SCHEMA(
        {
            "api_host": "http://192.168.86.32:8123",
            "io": {
                "1": "Switchable Output",
                "out": "Switchable Output",
            },
            "switches": [
                {
                    "zone": "1",
                    "name": "alarm",
                },
                {
                    "zone": "out",
                    "name": "switcher",
                    "activation": "low",
                    "momentary": 50,
                    "pause": 100,
                    "repeat": -1,
                },
            ],
        }
    )

    entry = MockConfigEntry(
        domain="konnected",
        title="Konnected Alarm Panel",
        data=device_config,
        options=device_options,
    )
    entry.add_to_hass(hass)

    assert (
        await async_setup_component(
            hass,
            konnected.DOMAIN,
            {konnected.DOMAIN: {konnected.CONF_ACCESS_TOKEN: "globaltoken"}},
        )
        is True
    )

    with patch(
        "homeassistant.components.konnected.panel.AlarmPanel.async_connect",
        return_value=True,
    ):

        assert await async_setup_entry(hass, entry) is True

    with patch(
        "homeassistant.components.konnected.panel.AlarmPanel.available",
        return_value=True,
    ):

        await hass.async_block_till_done()

        with patch(
            "homeassistant.components.konnected.panel.AlarmPanel.update_switch",
            return_value={"state": 0},
        ):

            # Turn switch off.
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: "switch.alarm"},
                blocking=True,
            )

            # Verify the switch turns off.
            entity_state = hass.states.get("switch.alarm")
            assert entity_state
            assert entity_state.state == "off"

        with patch(
            "homeassistant.components.konnected.panel.AlarmPanel.update_switch",
            return_value={"state": 1},
        ):

            # Turn switch on.
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: "switch.alarm"},
                blocking=True,
            )

            # Verify the switch turns on.
            entity_state = hass.states.get("switch.alarm")
            assert entity_state
            assert entity_state.state == "on"

            # Turn switch off.
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: "switch.alarm"},
                blocking=True,
            )

            # Verify the switch turns on.
            entity_state = hass.states.get("switch.alarm")
            assert entity_state
            assert entity_state.state == "on"

        # test with momentary to cover part of async_turn_on that is momentary only
        with patch(
            "homeassistant.components.konnected.panel.AlarmPanel.update_switch",
            return_value={"state": 1},
        ):
            # Turn switch on.
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: "switch.switcher"},
                blocking=True,
            )

            # Verify the switch turns on.
            entity_state = hass.states.get("switch.switcher")
            assert entity_state
            assert entity_state.state == "off"
