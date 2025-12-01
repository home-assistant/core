"""Services for the SQL integration."""

from __future__ import annotations

import logging

from sqlalchemy.engine import Result
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import voluptuous as vol

from homeassistant.components.recorder import CONF_DB_URL, get_instance
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger_template_entity import ValueTemplate
from homeassistant.util.json import JsonValueType

from .const import CONF_QUERY, DOMAIN
from .util import (
    async_create_sessionmaker,
    check_and_render_sql_query,
    convert_value,
    generate_lambda_stmt,
    redact_credentials,
    resolve_db_url,
    validate_query,
    validate_sql_select,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_QUERY = "query"
SERVICE_QUERY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_QUERY): vol.All(
            cv.template, ValueTemplate.from_template, validate_sql_select
        ),
        vol.Optional(CONF_DB_URL): cv.string,
    }
)


async def _async_query_service(
    call: ServiceCall,
) -> ServiceResponse:
    """Execute a SQL query service and return the result."""
    db_url = resolve_db_url(call.hass, call.data.get(CONF_DB_URL))
    query_str = call.data[CONF_QUERY]
    (
        sessmaker,
        uses_recorder_db,
        use_database_executor,
    ) = await async_create_sessionmaker(call.hass, db_url)
    try:
        validate_query(call.hass, query_str, uses_recorder_db, None)
    except ValueError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="query_not_allowed",
            translation_placeholders={"error": str(err)},
        ) from err
    if sessmaker is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="db_connection_failed",
            translation_placeholders={"db_url": redact_credentials(db_url)},
        )

    def _execute_and_convert_query() -> list[JsonValueType]:
        """Execute the query and return the results with converted types."""
        sess: Session = sessmaker()
        rendered_query = check_and_render_sql_query(call.hass, query_str)
        try:
            result: Result = sess.execute(generate_lambda_stmt(rendered_query))
        except SQLAlchemyError as err:
            _LOGGER.debug(
                "Error executing query %s: %s",
                query_str,
                redact_credentials(str(err)),
            )
            sess.rollback()
            raise
        else:
            rows: list[JsonValueType] = []
            for row in result.mappings():
                processed_row: dict[str, JsonValueType] = {}
                for key, value in row.items():
                    processed_row[key] = convert_value(value)
                rows.append(processed_row)
            return rows
        finally:
            sess.close()

    try:
        if use_database_executor:
            result = await get_instance(call.hass).async_add_executor_job(
                _execute_and_convert_query
            )
        else:
            result = await call.hass.async_add_executor_job(_execute_and_convert_query)
    except SQLAlchemyError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="query_execution_error",
            translation_placeholders={"error": redact_credentials(str(err))},
        ) from err

    return {"result": result}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the SQL integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_QUERY,
        _async_query_service,
        schema=SERVICE_QUERY_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
