"""Tests for the Mitsubishi WF-RAC integration."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from pywfrac import get_capabilities

from homeassistant.components.mitsubishi_wf_rac.const import (
    CONF_AIRCO_ID,
    CONF_OPERATOR_ID,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed

AIRCO_ID = "0011223344aa"
HOST = "192.168.1.4"
PORT = 51443

ENTRY_DATA = {
    CONF_HOST: HOST,
    CONF_DEVICE_ID: "homeassistant-device-0123456789a",
    CONF_OPERATOR_ID: "hassio-00000000-0000-0000-0000-000000000000",
    CONF_PORT: PORT,
    CONF_AIRCO_ID: AIRCO_ID,
}

POLL = timedelta(seconds=60)


def model(raw: int) -> dict[str, Any]:
    """Aircon fields that make the unit report this model byte."""
    return {"ModelNrRaw": raw, "Capabilities": get_capabilities(raw)}


async def advance_polls(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, polls: int = 1
) -> None:
    """Let the given number of polling intervals pass, one poll each."""
    for _ in range(polls):
        freezer.tick(POLL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
