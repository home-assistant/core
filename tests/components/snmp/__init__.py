"""Tests for the SNMP integration."""

from typing import Any

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.snmp.const import (
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_CONTEXT_NAME,
    CONF_VERSION,
    DEFAULT_COMMUNITY,
    DEFAULT_PORT,
    DEFAULT_VERSION,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE_TRACKER,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT

ARP_TABLE_MAC_OID = "1.3.6.1.2.1.4.22.1.2"

# Fixed so registry and snapshot expectations do not depend on a generated ULID
SUBENTRY_ID = "snmp_device_tracker"


def mock_entry(
    *,
    host: str = "192.168.1.1",
    baseoid: str | None = ARP_TABLE_MAC_OID,
    source: str = SOURCE_USER,
    **data: Any,
) -> MockConfigEntry:
    """Create an SNMP device entry, optionally with a device tracker subentry."""
    entry_data = {
        CONF_HOST: host,
        CONF_PORT: DEFAULT_PORT,
        CONF_VERSION: DEFAULT_VERSION,
        CONF_CONTEXT_NAME: "",
        **data,
    }
    if entry_data[CONF_VERSION] != "3":
        entry_data.setdefault(CONF_COMMUNITY, DEFAULT_COMMUNITY)
    return MockConfigEntry(
        domain=DOMAIN,
        source=source,
        title=host,
        data=entry_data,
        subentries_data=(
            []
            if baseoid is None
            else [
                {
                    "data": {CONF_BASEOID: baseoid},
                    "subentry_id": SUBENTRY_ID,
                    "subentry_type": SUBENTRY_TYPE_DEVICE_TRACKER,
                    "title": baseoid,
                    "unique_id": baseoid,
                }
            ]
        ),
    )
