"""Utils for sql."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import logging
from typing import Any

import sqlalchemy
from sqlalchemy import lambda_stmt
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.util import LRUCache
import sqlparse
import voluptuous as vol

from homeassistant.components.recorder import SupportedDialect, get_instance
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.template import Template

from .const import DB_URL_RE, DOMAIN
from .models import SQLData

_LOGGER = logging.getLogger(__name__)

_SQL_LAMBDA_CACHE: LRUCache = LRUCache(1000)


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


def validate_sql_select(value: Template) -> Template:
    """Validate that value is a SQL SELECT query."""
    try:
        assert value.hass
        check_and_render_sql_query(value.hass, value)
    except (TemplateError, InvalidSqlQuery) as err:
        raise vol.Invalid(str(err)) from err
    return value


async def async_create_sessionmaker(
    hass: HomeAssistant, db_url: str
) -> tuple[scoped_session | None, bool, bool]:
    """Create a session maker for the given db_url.

    This function gets or creates a SQLAlchemy `scoped_session` for the given
    db_url. It reuses existing connections where possible and handles the special
    case for the default recorder's database to use the correct executor.

    Args:
        hass: The Home Assistant instance.
        db_url: The database URL to connect to.

    Returns:
        A tuple containing the following items:
        - (scoped_session | None): The SQLAlchemy session maker for executing
          queries. This is `None` if a connection to the database could not
          be established.
        - (bool): A flag indicating if the query is against the recorder
          database.
        - (bool): A flag indicating if the dedicated recorder database
          executor should be used.

    """
    try:
        instance = get_instance(hass)
    except KeyError:  # No recorder loaded
        uses_recorder_db = False
    else:
        uses_recorder_db = db_url == instance.db_url
    sessmaker: scoped_session | None
    sql_data = _async_get_or_init_domain_data(hass)
    use_database_executor = False
    if uses_recorder_db and instance.dialect_name == SupportedDialect.SQLITE:
        use_database_executor = True
        assert instance.engine is not None
        sessmaker = scoped_session(sessionmaker(bind=instance.engine, future=True))
    # For other databases we need to create a new engine since
    # we want the connection to use the default timezone and these
    # database engines will use QueuePool as its only sqlite that
    # needs our custom pool. If there is already a session maker
    # for this db_url we can use that so we do not create a new engine
    # for every sensor.
    elif db_url in sql_data.session_makers_by_db_url:
        sessmaker = sql_data.session_makers_by_db_url[db_url]
    elif sessmaker := await hass.async_add_executor_job(
        _validate_and_get_session_maker_for_db_url, db_url
    ):
        sql_data.session_makers_by_db_url[db_url] = sessmaker
    else:
        return (None, uses_recorder_db, use_database_executor)

    return (sessmaker, uses_recorder_db, use_database_executor)


def validate_query(
    hass: HomeAssistant,
    query_template: str | Template,
    uses_recorder_db: bool,
    unique_id: str | None = None,
) -> None:
    """Validate the query against common performance issues.

    Args:
        hass: The Home Assistant instance.
        query_template: The SQL query string to be validated.
        uses_recorder_db: A boolean indicating if the query is against the recorder database.
        unique_id: The unique ID of the entity, used for creating issue registry keys.

    Raises:
        ValueError: If the query uses `entity_id` without referencing `states_meta`.

    """
    if not uses_recorder_db:
        return
    if isinstance(query_template, Template):
        query_str = query_template.async_render()
    else:
        query_str = Template(query_template, hass).async_render()
    redacted_query = redact_credentials(query_str)

    issue_key = unique_id if unique_id else redacted_query
    # If the query has a unique id and they fix it we can dismiss the issue
    # but if it doesn't have a unique id they have to ignore it instead

    upper_query = query_str.upper()
    if (
        "ENTITY_ID," in upper_query or "ENTITY_ID " in upper_query
    ) and "STATES_META" not in upper_query:
        _LOGGER.error(
            "The query `%s` contains the keyword `entity_id` but does not "
            "reference the `states_meta` table. This will cause a full table "
            "scan and database instability. Please check the documentation and use "
            "`states_meta.entity_id` instead",
            redacted_query,
        )

        ir.async_create_issue(
            hass,
            DOMAIN,
            f"entity_id_query_does_full_table_scan_{issue_key}",
            translation_key="entity_id_query_does_full_table_scan",
            translation_placeholders={"query": redacted_query},
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
        )
        raise ValueError("Query contains entity_id but does not reference states_meta")

    ir.async_delete_issue(
        hass, DOMAIN, f"entity_id_query_does_full_table_scan_{issue_key}"
    )


@callback
def _async_get_or_init_domain_data(hass: HomeAssistant) -> SQLData:
    """Get or initialize domain data."""
    if DOMAIN in hass.data:
        sql_data: SQLData = hass.data[DOMAIN]
        return sql_data

    session_makers_by_db_url: dict[str, scoped_session] = {}

    #
    # Ensure we dispose of all engines at shutdown
    # to avoid unclean disconnects
    #
    # Shutdown all sessions in the executor since they will
    # do blocking I/O
    #
    def _shutdown_db_engines(event: Event) -> None:
        """Shutdown all database engines."""
        for sessmaker in session_makers_by_db_url.values():
            sessmaker.connection().engine.dispose()

    cancel_shutdown = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, _shutdown_db_engines
    )

    sql_data = SQLData(cancel_shutdown, session_makers_by_db_url)
    hass.data[DOMAIN] = sql_data
    return sql_data


def _validate_and_get_session_maker_for_db_url(db_url: str) -> scoped_session | None:
    """Validate the db_url and return a session maker.

    This does I/O and should be run in the executor.
    """
    sess: Session | None = None
    try:
        engine = sqlalchemy.create_engine(db_url, future=True)
        sessmaker = scoped_session(sessionmaker(bind=engine, future=True))
        # Run a dummy query just to test the db_url
        sess = sessmaker()
        sess.execute(sqlalchemy.text("SELECT 1;"))

    except SQLAlchemyError as err:
        _LOGGER.error(
            "Couldn't connect using %s DB_URL: %s",
            redact_credentials(db_url),
            redact_credentials(str(err)),
        )
        return None
    else:
        return sessmaker
    finally:
        if sess:
            sess.close()


def generate_lambda_stmt(query: str) -> StatementLambdaElement:
    """Generate the lambda statement."""
    text = sqlalchemy.text(query)
    return lambda_stmt(lambda: text, lambda_cache=_SQL_LAMBDA_CACHE)


def convert_value(value: Any) -> Any:
    """Convert value."""
    match value:
        case Decimal():
            return float(value)
        case date():
            return value.isoformat()
        case bytes() | bytearray():
            return f"0x{value.hex()}"
        case _:
            return value


def check_and_render_sql_query(hass: HomeAssistant, query: Template | str) -> str:
    """Check and render SQL query."""
    if isinstance(query, str):
        query = query.strip()
        if not query:
            raise EmptyQueryError("Query cannot be empty")
        query = Template(query, hass=hass)

    # Raises TemplateError if template is invalid
    query.ensure_valid()
    rendered_query: str = query.async_render()

    if len(rendered_queries := sqlparse.parse(rendered_query.lstrip().lstrip(";"))) > 1:
        raise MultipleQueryError("Multiple SQL statements are not allowed")
    if (
        len(rendered_queries) == 0
        or (query_type := rendered_queries[0].get_type()) == "UNKNOWN"
    ):
        raise UnknownQueryTypeError("SQL query is empty or unknown type")
    if query_type != "SELECT":
        _LOGGER.debug("The SQL query %s is of type %s", rendered_query, query_type)
        raise NotSelectQueryError("SQL query must be of type SELECT")

    return str(rendered_queries[0])


class InvalidSqlQuery(HomeAssistantError):
    """SQL query is invalid error."""


class EmptyQueryError(InvalidSqlQuery):
    """SQL query is empty error."""


class MultipleQueryError(InvalidSqlQuery):
    """SQL query is multiple error."""


class UnknownQueryTypeError(InvalidSqlQuery):
    """SQL query is of unknown type error."""


class NotSelectQueryError(InvalidSqlQuery):
    """SQL query is not a SELECT statement error."""
