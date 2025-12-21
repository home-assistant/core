"""The sql integration models."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import scoped_session

from homeassistant.core import CALLBACK_TYPE


@dataclass(slots=True)
class SQLData:
    """Data for the sql integration."""

    shutdown_event_cancel: CALLBACK_TYPE
    session_makers_by_db_url: dict[str, scoped_session]
