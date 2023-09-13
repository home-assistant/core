"""Helper functions of Minecraft Server integration."""
import logging
from typing import Any

import aiodns

from homeassistant.const import CONF_HOST, CONF_PORT

from .const import SRV_RECORD_PREFIX

_LOGGER = logging.getLogger(__name__)


async def async_check_srv_record(host: str) -> dict[str, Any] | None:
    """Check if the given host is a valid Minecraft SRV record."""
    srv_record = None

    try:
        srv_query = await aiodns.DNSResolver().query(
            host=f"{SRV_RECORD_PREFIX}.{host}", qtype="SRV"
        )
    except aiodns.error.DNSError:
        # 'host' is not a Minecraft SRV record.
        pass
    else:
        # 'host' is a valid Minecraft SRV record, extract the data.
        srv_record = {
            CONF_HOST: srv_query[0].host,
            CONF_PORT: srv_query[0].port,
        }
        _LOGGER.debug(
            "'%s' is a valid Minecraft SRV record ('%s:%s')",
            host,
            srv_record[CONF_HOST],
            srv_record[CONF_PORT],
        )

    return srv_record
