"""The sql integration models."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session
from sqlalchemy.orm import Session, scoped_session

from homeassistant.core import CALLBACK_TYPE


@dataclass(slots=True)
class SQLData:
    """Data for the sql integration."""

    shutdown_event_cancel: CALLBACK_TYPE
    session_makers_by_db_url: dict[
        str, async_scoped_session[AsyncSession] | scoped_session[Session]
    ]
