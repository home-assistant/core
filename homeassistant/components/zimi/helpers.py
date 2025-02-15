"""The zcc integration helpers."""

from __future__ import annotations

import logging

from zcc import ControlPoint, ControlPointDescription, ControlPointError

from homeassistant.exceptions import ConfigEntryNotReady

_LOGGER = logging.getLogger(__name__)


async def async_connect_to_controller(
    host: str, port: int, fast: bool = False
) -> ControlPoint | None:
    """Connect to Zimi Cloud Controller with defined parameters."""

    _LOGGER.debug("Connecting to %s:%d", host, port)

    api = ControlPoint(
        description=ControlPointDescription(
            host=host,
            port=port,
        )
    )
    try:
        await api.connect(fast=fast)

    except ControlPointError as error:
        _LOGGER.error("Connection failed: %s", error)
        raise ConfigEntryNotReady(error) from error

    if api.ready:
        _LOGGER.debug("Connected")

        if not fast:
            api.start_watchdog()
            _LOGGER.debug("Started watchdog")

        return api

    msg = "Connection failed: not ready"
    _LOGGER.error(msg=msg)

    raise ConfigEntryNotReady
