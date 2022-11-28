"""Helper functions for the Minecraft Server integration."""
from __future__ import annotations

from typing import Any

import aiodns

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import SRV_RECORD_PREFIX


async def async_check_srv_record(
    hass: HomeAssistant, host: str
) -> dict[str, Any] | None:
    """Check if the given host is a valid Minecraft SRV record."""
    # Check if 'host' is a valid SRV record.
    return_value = None
    srv_records = None
    try:
        srv_records = await aiodns.DNSResolver().query(
            host=f"{SRV_RECORD_PREFIX}.{host}", qtype="SRV"
        )
    except (aiodns.error.DNSError):
        # 'host' is not a SRV record.
        pass
    else:
        # 'host' is a valid SRV record, extract the data.
        return_value = {
            CONF_HOST: srv_records[0].host,
            CONF_PORT: srv_records[0].port,
        }

    return return_value
