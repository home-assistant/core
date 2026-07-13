"""Init."""

import logging

import aiohttp
from defusedxml import ElementTree as ET

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "papouch"


def parse_quido_xml(raw_xml: str) -> dict:
    """Parsing data."""
    # TODO: it's hardcoded for quido, need rework for other devices
    root = ET.fromstring(raw_xml)

    parsed_data = {"temp": {}, "din": {}, "dout": {}}

    for element in root:
        if element.tag in ["temp", "din", "dout"]:
            item_id = element.attrib.get("id")
            val_str = element.attrib.get("val", "0")

            if element.tag == "temp":
                parsed_data[element.tag][item_id] = float(val_str)
            else:
                parsed_data[element.tag][item_id] = int(val_str)

    return parsed_data


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Setup. Note that polling is used with HTTP 1.0."""
    session = async_get_clientsession(hass)

    headers = {"User-Agent": "curl/8.14.1", "Accept": "*/*", "Connection": "close"}

    try:
        # TODO: change it to prevent hard-coded IP (even though it probably will be the same)
        async with session.get(
            "http://192.168.3.31/fresh.xml", headers=headers
        ) as response:
            data = await response.text(encoding="iso-8859-2")

            if data:
                parsed_data = parse_quido_xml(data)
                # TODO: create a Option flow
                # TODO: do something with that data
                return True

    except aiohttp.ClientError as err:
        _LOGGER.error("Error connecting to device: %s", err)

    return False
