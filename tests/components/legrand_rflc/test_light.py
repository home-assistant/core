"""Tests for the Legrand RFLC component light platform."""
import asyncio
import logging
from typing import Final

import lc7001.aio

from homeassistant.components.legrand_rflc.const import DOMAIN
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HOST,
    CONF_PORT,
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
)

from .emulation import Server

from tests.common import MockConfigEntry
from tests.components.light import common

_LOGGER: Final = logging.getLogger(__name__)

COMPOSER: Final = lc7001.aio.Composer()


async def test_light(hass, socket_enabled):
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
            b'{"ID":0,"Service":"ZonePropertiesChanged","ZID":1,"PropertyList":{"Power":false},"Status":"Success"}\x00{"ID":8,"Service":"SetZoneProperties","Status":"Success"}\x00',
        ],
    ]

    class EventAuditor:
        def __init__(self):
            self.queue = asyncio.Queue()

        async def start(self):
            SWITCH: Final = "light.switch"
            DIMMER: Final = "light.dimmer"

            entity_ids = {SWITCH, DIMMER}

            expect = [
                [SWITCH, STATE_OFF],
                [DIMMER, STATE_OFF],
                [SWITCH, STATE_ON],
                [SWITCH, STATE_OFF],
                [DIMMER, STATE_ON, 255],
                [DIMMER, STATE_ON, 127],
                [DIMMER, STATE_OFF],
            ]

            hass.bus.async_listen(
                EVENT_STATE_CHANGED,
                lambda event: self.queue.put_nowait(event),
            )

            while len(expect):
                event = await self.queue.get()
                self.queue.task_done()
                state = event.data.get("new_state")
                entity_id = state.entity_id
                if state.state == STATE_ON or state.state == STATE_OFF:
                    attributes = state.attributes
                    got = [entity_id, state.state]
                    if ATTR_BRIGHTNESS in attributes:
                        got.append(attributes[ATTR_BRIGHTNESS])
                    assert expect.pop(0) == got
                if entity_id in entity_ids:
                    entity_ids.remove(entity_id)
                    if len(entity_ids) == 0:

                        async def incite():
                            await common.async_turn_on(hass, entity_id=SWITCH)
                            await common.async_turn_off(hass, entity_id=SWITCH)
                            await common.async_turn_on(hass, entity_id=DIMMER)
                            await common.async_turn_on(
                                hass,
                                entity_id=DIMMER,
                                brightness_pct=50,
                                transition=60,
                            )
                            await common.async_turn_off(hass, entity_id=DIMMER)

                        hass.async_create_task(incite())

    hass.async_create_task(EventAuditor().start())

    # start an emulated server for our client's session
    server_port = await Server(hass, sessions).start(False)

    # create a mock config entry referencing emulated server
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTHENTICATION: Server.AUTHENTICATION,
            CONF_HOST: Server.HOST,
            CONF_PORT: server_port,
        },
    )
    entry.add_to_hass(hass)

    # setup config entry (this will start our client)
    hass.async_create_task(hass.config_entries.async_setup(entry.entry_id))

    # wait until our client's session with the server is complete
    await hass.async_block_till_done()

    # unload the client
    await hass.config_entries.async_unload(entry.entry_id)
