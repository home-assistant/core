"""Helper functions for the Minecraft Server integration."""

from functools import partial
from typing import Any, Dict

import dns.resolver

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.typing import HomeAssistantType

from .const import SRV_RECORD_PREFIX


async def async_check_srv_record(hass: HomeAssistantType, host: str) -> Dict[str, Any]:
    """Check if the given host is a valid Minecraft SRV record."""
    # Check if 'host' is a valid SRV record.
    return_value = None
    srv_records = None
    try:
        params = {
            "qname": f"{SRV_RECORD_PREFIX}.{host}",
            "rdtype": dns.rdatatype.SRV,
        }
        srv_records = await hass.async_add_executor_job(
            partial(dns.resolver.query, **params)
        )
    except (
        dns.exception.Timeout,
        dns.resolver.NoAnswer,
        dns.resolver.NoNameservers,
        dns.resolver.NXDOMAIN,
        dns.resolver.YXDOMAIN,
    ):
        # 'host' is not a SRV record.
        pass
    else:
        # 'host' is a valid SRV record, extract the data.
        return_value = {
            CONF_HOST: str(srv_records[0].target).rstrip("."),
            CONF_PORT: srv_records[0].port,
        }

    return return_value
