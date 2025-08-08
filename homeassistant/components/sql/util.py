"""Utils for sql."""

from __future__ import annotations

import logging

import sqlparse

from homeassistant.components.recorder import get_instance
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import Template

from .const import DB_URL_RE

_LOGGER = logging.getLogger(__name__)


def redact_credentials(data: str | None) -> str:
    """Redact credentials from string data."""
    if not data:
        return "none"
    return DB_URL_RE.sub("//****:****@", data)


def resolve_db_url(hass: HomeAssistant, db_url: str | None) -> str:
    """Return the db_url provided if not empty, otherwise return the recorder db_url."""
    _LOGGER.debug("db_url: %s", redact_credentials(db_url))
    if db_url and not db_url.isspace():
        return db_url
    return get_instance(hass).db_url


def check_and_render_sql_query(hass: HomeAssistant, query: Template | str) -> str:
    """Check and render SQL query."""
    if isinstance(query, str):
        query = query.strip()
        if not query:
            raise ValueError("Query cannot be empty")
        query = Template(query, hass=hass)

    try:
        query.ensure_valid()
        rendered_query: str = query.async_render()
    except TemplateError as err:
        raise ValueError("Invalid template") from err
    if len(rendered_queries := sqlparse.parse(rendered_query.lstrip().lstrip(";"))) > 1:
        raise ValueError("Multiple SQL statements are not allowed")
    if (
        len(rendered_queries) == 0
        or (query_type := rendered_queries[0].get_type()) == "UNKNOWN"
    ):
        raise ValueError("SQL query is empty or unknown type")
    if query_type != "SELECT":
        _LOGGER.debug("The SQL query %s is of type %s", rendered_query, query_type)
        raise ValueError("SQL query must be of type SELECT")

    return str(rendered_queries[0])
