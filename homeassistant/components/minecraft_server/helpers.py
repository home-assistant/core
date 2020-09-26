"""Helper functions for the Minecraft Server integration."""

from typing import Any, Dict

import aiodns

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.typing import HomeAssistantType

from .const import SRV_RECORD_PREFIX


async def async_check_srv_record(hass: HomeAssistantType, host: str) -> Dict[str, Any]:
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
