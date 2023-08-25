"""Tests for the IPP integration."""
from collections.abc import Mapping
from typing import Any

from homeassistant.components import zeroconf
from homeassistant.components.ipp.const import CONF_BASE_PATH, DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

ATTR_HOSTNAME = "hostname"
ATTR_PROPERTIES = "properties"

HOST = "192.168.1.31"
PORT = 631
BASE_PATH = "/ipp/print"

IPP_ZEROCONF_SERVICE_TYPE = "_ipp._tcp.local."
IPPS_ZEROCONF_SERVICE_TYPE = "_ipps._tcp.local."

ZEROCONF_NAME = "EPSON XP-6000 Series"
ZEROCONF_HOST = HOST
ZEROCONF_HOSTNAME = "EPSON123456.local."
ZEROCONF_PORT = PORT
ZEROCONF_RP = "ipp/print"

MOCK_USER_INPUT = {
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_SSL: False,
    CONF_VERIFY_SSL: False,
    CONF_BASE_PATH: BASE_PATH,
}

MOCK_ZEROCONF_IPP_SERVICE_INFO = zeroconf.ZeroconfServiceInfo(
    type=IPP_ZEROCONF_SERVICE_TYPE,
    name=f"{ZEROCONF_NAME}.{IPP_ZEROCONF_SERVICE_TYPE}",
    host=ZEROCONF_HOST,
    addresses=[ZEROCONF_HOST],
    hostname=ZEROCONF_HOSTNAME,
    port=ZEROCONF_PORT,
    properties={"rp": ZEROCONF_RP},
)

MOCK_ZEROCONF_IPPS_SERVICE_INFO = zeroconf.ZeroconfServiceInfo(
    type=IPPS_ZEROCONF_SERVICE_TYPE,
    name=f"{ZEROCONF_NAME}.{IPPS_ZEROCONF_SERVICE_TYPE}",
    host=ZEROCONF_HOST,
    addresses=[ZEROCONF_HOST],
    hostname=ZEROCONF_HOSTNAME,
    port=ZEROCONF_PORT,
    properties={"rp": ZEROCONF_RP},
)


def register_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    domain: str,
    object_id: str,
    unique_id: str,
    config_entry: ConfigEntry | None = None,
    capabilities: Mapping[str, Any] | None = None,
) -> str:
    """Register enabled entity, return entity_id."""
    entity_registry.async_get_or_create(
        domain,
        DOMAIN,
        f"cfe92100-67c4-11d4-a45f-f8d027761251_{unique_id}",
        suggested_object_id=object_id,
        disabled_by=None,
        config_entry=config_entry,
        capabilities=capabilities,
    )

    return f"{domain}.{object_id}"
