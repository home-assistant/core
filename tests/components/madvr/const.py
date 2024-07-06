"""Constants for the MadVR tests."""

from homeassistant.components.madvr.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry

MOCK_CONFIG = {
    CONF_HOST: "192.168.1.1",
    CONF_PORT: 44077,
}

MOCK_MAC = "00:11:22:33:44:55"

CONFIG_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    data=MOCK_CONFIG,
    unique_id=MOCK_MAC,
)
