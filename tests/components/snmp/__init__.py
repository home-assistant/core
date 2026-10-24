"""Tests for the SNMP integration."""

from homeassistant.components.snmp.const import (
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_CONTEXT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE_TRACKER,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry

ARP_TABLE_MAC_OID = "1.3.6.1.2.1.4.22.1.2"


def mock_entry(
    *,
    host: str = "192.168.1.1",
    community: str = "public",
    baseoid: str | None = ARP_TABLE_MAC_OID,
    source: str = SOURCE_USER,
) -> MockConfigEntry:
    """Create an SNMP device entry, optionally with a device tracker subentry."""
    return MockConfigEntry(
        domain=DOMAIN,
        source=source,
        title=host,
        data={
            CONF_HOST: host,
            CONF_PORT: DEFAULT_PORT,
            CONF_COMMUNITY: community,
            CONF_CONTEXT_NAME: "",
        },
        subentries_data=(
            []
            if baseoid is None
            else [
                {
                    "data": {CONF_BASEOID: baseoid},
                    "subentry_type": SUBENTRY_TYPE_DEVICE_TRACKER,
                    "title": "Device tracker",
                    "unique_id": SUBENTRY_TYPE_DEVICE_TRACKER,
                }
            ]
        ),
    )
