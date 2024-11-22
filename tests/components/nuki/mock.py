"""Mockup Nuki device."""

from homeassistant.components.nuki.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture

NAME = "Nuki_Bridge_BC614E"
HOST = "1.1.1.1"
MAC = "01:23:45:67:89:ab"
DHCP_FORMATTED_MAC = "0123456789ab"

HW_ID = 12345678
ID_HEX = "BC614E"

MOCK_INFO = load_json_object_fixture("info.json", DOMAIN)


async def setup_nuki_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Create the Nuki device."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ID_HEX,
        data={CONF_HOST: HOST, CONF_PORT: 8080, CONF_TOKEN: "test-token"},
    )
    entry.add_to_hass(hass)

    return entry
