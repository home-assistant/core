"""Tests for the Legrand RFLC component light platform."""
import logging
from typing import Final

import lc7001.aio

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.const import EVENT_STATE_CHANGED, STATE_OFF, STATE_ON

from .emulation import Server

from tests.components.light import common

_LOGGER: Final = logging.getLogger(__name__)


COMPOSER: Final = lc7001.aio.Composer()


async def test_light(hass):
    """Test light platform."""
    sessions = [
        [
            Server.SECURITY_NON_COMPLIANT,
            COMPOSER.wrap(1, COMPOSER.compose_list_zones()),
            b'{"ID":1,"Service":"ListZones","ZoneList":[{"ZID":0},{"ZID":1}],"Status":"Success"}\x00',
            COMPOSER.wrap(2, COMPOSER.compose_report_zone_properties(0)),
            b'{"ID":2,"Service":"ReportZoneProperties","ZID":0,"PropertyList":{"Name":"switch","DeviceType":"Switch","Power":false},"Status":"Success"}\x00',
            COMPOSER.wrap(3, COMPOSER.compose_report_zone_properties(1)),
            b'{"ID":3,"Service":"ReportZoneProperties","ZID":1,"PropertyList":{"Name":"dimmer","DeviceType":"Dimmer","PowerLevel":100,"Power":false},"Status":"Success"}\x00',
            COMPOSER.wrap(4, COMPOSER.compose_set_zone_properties(0, power=True)),
            b'{"ID":0,"Service":"ZonePropertiesChanged","ZID":0,"PropertyList":{"Power":true},"Status":"Success"}\x00{"ID":4,"Service":"SetZoneProperties","Status":"Success"}\x00',
            COMPOSER.wrap(5, COMPOSER.compose_set_zone_properties(0, power=False)),
            b'{"ID":0,"Service":"ZonePropertiesChanged","ZID":0,"PropertyList":{"Power":false},"Status":"Success"}\x00{"ID":5,"Service":"SetZoneProperties","Status":"Success"}\x00',
            COMPOSER.wrap(6, COMPOSER.compose_set_zone_properties(1, power=True)),
            b'{"ID":0,"Service":"ZonePropertiesChanged","ZID":1,"PropertyList":{"Power":true},"Status":"Success"}\x00{"ID":6,"Service":"SetZoneProperties","Status":"Success"}\x00',
            COMPOSER.wrap(
                7,
                COMPOSER.compose_set_zone_properties(
                    1, power=True, power_level=50, ramp_rate=1
                ),
            ),
            b'{"ID":0,"Service":"ZonePropertiesChanged","ZID":1,"PropertyList":{"PowerLevel":50,"Power":true},"Status":"Success"}\x00{"ID":7,"Service":"SetZoneProperties","Status":"Success"}\x00',
            COMPOSER.wrap(8, COMPOSER.compose_set_zone_properties(1, power=False)),
            b'{"ID":0,"Service":"ZonePropertiesChanged","ZID":1,"PropertyList":{"PowerLevel":50,"Power":false},"Status":"Success"}\x00{"ID":8,"Service":"SetZoneProperties","Status":"Success"}\x00',
        ],
    ]

    LIGHT_SWITCH: Final = "light.switch"
    LIGHT_DIMMER: Final = "light.dimmer"

    entity_ids = {LIGHT_SWITCH, LIGHT_DIMMER}

    state_changed_expect = [
        [LIGHT_SWITCH, STATE_OFF],
        [LIGHT_DIMMER, STATE_OFF],
        [LIGHT_SWITCH, STATE_ON],
        [LIGHT_SWITCH, STATE_OFF],
        [LIGHT_DIMMER, STATE_ON, 255],
        [LIGHT_DIMMER, STATE_ON, 127],
        [LIGHT_DIMMER, STATE_OFF],
    ]

    def state_changed(event):
        state = event.data.get("new_state")
        entity_id = state.entity_id
        if state.state == STATE_ON or state.state == STATE_OFF:
            attributes = state.attributes
            got = [entity_id, state.state]
            if ATTR_BRIGHTNESS in attributes:
                got.append(attributes[ATTR_BRIGHTNESS])
            assert state_changed_expect.pop(0) == got
        if entity_id in entity_ids:
            entity_ids.remove(entity_id)
            if len(entity_ids) == 0:

                async def dance():
                    await common.async_turn_on(hass, entity_id=LIGHT_SWITCH)
                    await common.async_turn_off(hass, entity_id=LIGHT_SWITCH)
                    await common.async_turn_on(hass, entity_id=LIGHT_DIMMER)
                    await common.async_turn_on(
                        hass, entity_id=LIGHT_DIMMER, brightness_pct=50, transition=60
                    )
                    await common.async_turn_off(hass, entity_id=LIGHT_DIMMER)

                hass.async_create_task(dance())

    hass.bus.async_listen(EVENT_STATE_CHANGED, state_changed)
    await Server(hass, sessions).start()
