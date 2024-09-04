"""Helpers to check recorder."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
import functools
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from sqlalchemy.orm.session import Session

    from homeassistant.components.recorder import Recorder

_LOGGER = logging.getLogger(__name__)

DOMAIN: HassKey[RecorderData] = HassKey("recorder")
DATA_INSTANCE: HassKey[Recorder] = HassKey("recorder_instance")


@dataclass(slots=True)
class RecorderData:
    """Recorder data stored in hass.data."""

    recorder_platforms: dict[str, Any] = field(default_factory=dict)
    db_connected: asyncio.Future[bool] = field(default_factory=asyncio.Future)


@callback
def async_migration_in_progress(hass: HomeAssistant) -> bool:
    """Check to see if a recorder migration is in progress."""
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components import recorder

    return recorder.util.async_migration_in_progress(hass)


@callback
def async_migration_is_live(hass: HomeAssistant) -> bool:
    """Check to see if a recorder migration is live."""
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components import recorder

    return recorder.util.async_migration_is_live(hass)


@callback
def async_initialize_recorder(hass: HomeAssistant) -> None:
    """Initialize recorder data."""
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components.recorder.basic_websocket_api import async_setup

    hass.data[DOMAIN] = RecorderData()
    async_setup(hass)


async def async_wait_recorder(hass: HomeAssistant) -> bool:
    """Wait for recorder to initialize and return connection status.

    Returns False immediately if the recorder is not enabled.
    """
    if DOMAIN not in hass.data:
        return False
    return await hass.data[DOMAIN].db_connected


@functools.lru_cache(maxsize=1)
def get_instance(hass: HomeAssistant) -> Recorder:
    """Get the recorder instance."""
    return hass.data[DATA_INSTANCE]


@contextmanager
def session_scope(
    *,
    hass: HomeAssistant | None = None,
    session: Session | None = None,
    exception_filter: Callable[[Exception], bool] | None = None,
    read_only: bool = False,
) -> Generator[Session]:
    """Provide a transactional scope around a series of operations.

    read_only is used to indicate that the session is only used for reading
    data and that no commit is required. It does not prevent the session
    from writing and is not a security measure.
    """
    if session is None and hass is not None:
        session = get_instance(hass).get_session()

    if session is None:
        raise RuntimeError("Session required")

    need_rollback = False
    try:
        yield session
        if not read_only and session.get_transaction():
            need_rollback = True
            session.commit()
    except Exception as err:
        _LOGGER.exception("Error executing query")
        if need_rollback:
            session.rollback()
        if not exception_filter or not exception_filter(err):
            raise
    finally:
        session.close()
