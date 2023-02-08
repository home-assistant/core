"""Queries for logbook."""
from __future__ import annotations

from typing import Final

import sqlalchemy
from sqlalchemy import select
from sqlalchemy.sql.elements import BooleanClauseList, ColumnElement
from sqlalchemy.sql.expression import literal
from sqlalchemy.sql.selectable import Select

from homeassistant.components.recorder.db_schema import (
    EVENTS_CONTEXT_ID_INDEX,
    OLD_FORMAT_ATTRS_JSON,
    OLD_STATE,
    SHARED_ATTRS_JSON,
    STATES_CONTEXT_ID_INDEX,
    EventData,
    Events,
    StateAttributes,
    States,
)
from homeassistant.components.recorder.filters import like_domain_matchers

from ..const import ALWAYS_CONTINUOUS_DOMAINS, CONDITIONALLY_CONTINUOUS_DOMAINS

# Domains that are continuous if there is a UOM set on the entity
CONDITIONALLY_CONTINUOUS_ENTITY_ID_LIKE = like_domain_matchers(
    CONDITIONALLY_CONTINUOUS_DOMAINS
)
# Domains that are always continuous
ALWAYS_CONTINUOUS_ENTITY_ID_LIKE = like_domain_matchers(ALWAYS_CONTINUOUS_DOMAINS)

UNIT_OF_MEASUREMENT_JSON = '"unit_of_measurement":'
UNIT_OF_MEASUREMENT_JSON_LIKE = f"%{UNIT_OF_MEASUREMENT_JSON}%"

PSEUDO_EVENT_STATE_CHANGED: Final = None
# Since we don't store event_types and None
# and we don't store state_changed in events
# we use a NULL for state_changed events
# when we synthesize them from the states table
# since it avoids another column being sent
# in the payload

EVENT_COLUMNS = (
    Events.event_id.label("event_id"),
    Events.event_type.label("event_type"),
    Events.event_data.label("event_data"),
    Events.time_fired_ts.label("time_fired_ts"),
    Events.context_id.label("context_id"),
    Events.context_user_id.label("context_user_id"),
    Events.context_parent_id.label("context_parent_id"),
)

STATE_COLUMNS = (
    States.state_id.label("state_id"),
    States.state.label("state"),
    States.entity_id.label("entity_id"),
    SHARED_ATTRS_JSON["icon"].as_string().label("icon"),
    OLD_FORMAT_ATTRS_JSON["icon"].as_string().label("old_format_icon"),
)

STATE_CONTEXT_ONLY_COLUMNS = (
    States.state_id.label("state_id"),
    States.state.label("state"),
    States.entity_id.label("entity_id"),
    literal(value=None, type_=sqlalchemy.String).label("icon"),
    literal(value=None, type_=sqlalchemy.String).label("old_format_icon"),
)

EVENT_COLUMNS_FOR_STATE_SELECT = (
    literal(value=None, type_=sqlalchemy.Text).label("event_id"),
    # We use PSEUDO_EVENT_STATE_CHANGED aka None for
    # state_changed events since it takes up less
    # space in the response and every row has to be
    # marked with the event_type
    literal(value=PSEUDO_EVENT_STATE_CHANGED, type_=sqlalchemy.String).label(
        "event_type"
    ),
    literal(value=None, type_=sqlalchemy.Text).label("event_data"),
    States.last_updated_ts.label("time_fired_ts"),
    States.context_id.label("context_id"),
    States.context_user_id.label("context_user_id"),
    States.context_parent_id.label("context_parent_id"),
    literal(value=None, type_=sqlalchemy.Text).label("shared_data"),
)

EMPTY_STATE_COLUMNS = (
    literal(value=0, type_=sqlalchemy.Integer).label("state_id"),
    literal(value=None, type_=sqlalchemy.String).label("state"),
    literal(value=None, type_=sqlalchemy.String).label("entity_id"),
    literal(value=None, type_=sqlalchemy.String).label("icon"),
    literal(value=None, type_=sqlalchemy.String).label("old_format_icon"),
)


EVENT_ROWS_NO_STATES = (
    *EVENT_COLUMNS,
    EventData.shared_data.label("shared_data"),
    *EMPTY_STATE_COLUMNS,
)

# Virtual column to tell logbook if it should avoid processing
# the event as its only used to link contexts
CONTEXT_ONLY = literal(value="1", type_=sqlalchemy.String).label("context_only")
NOT_CONTEXT_ONLY = literal(value=None, type_=sqlalchemy.String).label("context_only")


def select_events_context_id_subquery(
    start_day: float,
    end_day: float,
    event_types: tuple[str, ...],
) -> Select:
    """Generate the select for a context_id subquery."""
    return (
        select(Events.context_id)
        .where((Events.time_fired_ts > start_day) & (Events.time_fired_ts < end_day))
        .where(Events.event_type.in_(event_types))
        .outerjoin(EventData, (Events.data_id == EventData.data_id))
    )


def select_events_context_only() -> Select:
    """Generate an events query that mark them as for context_only.

    By marking them as context_only we know they are only for
    linking context ids and we can avoid processing them.
    """
    return select(*EVENT_ROWS_NO_STATES, CONTEXT_ONLY)


def select_states_context_only() -> Select:
    """Generate an states query that mark them as for context_only.

    By marking them as context_only we know they are only for
    linking context ids and we can avoid processing them.
    """
    return select(
        *EVENT_COLUMNS_FOR_STATE_SELECT, *STATE_CONTEXT_ONLY_COLUMNS, CONTEXT_ONLY
    )


def select_events_without_states(
    start_day: float, end_day: float, event_types: tuple[str, ...]
) -> Select:
    """Generate an events select that does not join states."""
    return (
        select(*EVENT_ROWS_NO_STATES, NOT_CONTEXT_ONLY)
        .where((Events.time_fired_ts > start_day) & (Events.time_fired_ts < end_day))
        .where(Events.event_type.in_(event_types))
        .outerjoin(EventData, (Events.data_id == EventData.data_id))
    )


def select_states() -> Select:
    """Generate a states select that formats the states table as event rows."""
    return select(
        *EVENT_COLUMNS_FOR_STATE_SELECT,
        *STATE_COLUMNS,
        NOT_CONTEXT_ONLY,
    )


def legacy_select_events_context_id(
    start_day: float, end_day: float, context_id: str
) -> Select:
    """Generate a legacy events context id select that also joins states."""
    # This can be removed once we no longer have event_ids in the states table
    return (
        select(
            *EVENT_COLUMNS,
            literal(value=None, type_=sqlalchemy.String).label("shared_data"),
            *STATE_COLUMNS,
            NOT_CONTEXT_ONLY,
        )
        .outerjoin(States, (Events.event_id == States.event_id))
        .where(
            (States.last_updated_ts == States.last_changed_ts)
            | States.last_changed_ts.is_(None)
        )
        .where(_not_continuous_entity_matcher())
        .outerjoin(
            StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
        )
        .where((Events.time_fired_ts > start_day) & (Events.time_fired_ts < end_day))
        .where(Events.context_id == context_id)
    )


def apply_states_filters(sel: Select, start_day: float, end_day: float) -> Select:
    """Filter states by time range.

    Filters states that do not have an old state or new state (added / removed)
    Filters states that are in a continuous domain with a UOM.
    Filters states that do not have matching last_updated_ts and last_changed_ts.
    """
    return (
        sel.filter(
            (States.last_updated_ts > start_day) & (States.last_updated_ts < end_day)
        )
        .outerjoin(OLD_STATE, (States.old_state_id == OLD_STATE.state_id))
        .where(_missing_state_matcher())
        .where(_not_continuous_entity_matcher())
        .where(
            (States.last_updated_ts == States.last_changed_ts)
            | States.last_changed_ts.is_(None)
        )
        .outerjoin(
            StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
        )
    )


def _missing_state_matcher() -> ColumnElement[bool]:
    # The below removes state change events that do not have
    # and old_state or the old_state is missing (newly added entities)
    # or the new_state is missing (removed entities)
    return sqlalchemy.and_(
        OLD_STATE.state_id.is_not(None),
        (States.state != OLD_STATE.state),
        States.state.is_not(None),
    )


def _not_continuous_entity_matcher() -> ColumnElement[bool]:
    """Match non continuous entities."""
    return sqlalchemy.or_(
        # First exclude domains that may be continuous
        _not_possible_continuous_domain_matcher(),
        # But let in the entities in the possible continuous domains
        # that are not actually continuous sensors because they lack a UOM
        sqlalchemy.and_(
            _conditionally_continuous_domain_matcher, _not_uom_attributes_matcher()
        ).self_group(),
    )


def _not_possible_continuous_domain_matcher() -> ColumnElement[bool]:
    """Match not continuous domains.

    This matches domain that are always considered continuous
    and domains that are conditionally (if they have a UOM)
    continuous domains.
    """
    return sqlalchemy.and_(
        *[
            ~States.entity_id.like(entity_domain)
            for entity_domain in (
                *ALWAYS_CONTINUOUS_ENTITY_ID_LIKE,
                *CONDITIONALLY_CONTINUOUS_ENTITY_ID_LIKE,
            )
        ],
    ).self_group()


def _conditionally_continuous_domain_matcher() -> ColumnElement[bool]:
    """Match conditionally continuous domains.

    This matches domain that are only considered
    continuous if a UOM is set.
    """
    return sqlalchemy.or_(
        *[
            States.entity_id.like(entity_domain)
            for entity_domain in CONDITIONALLY_CONTINUOUS_ENTITY_ID_LIKE
        ],
    ).self_group()


def _not_uom_attributes_matcher() -> BooleanClauseList:
    """Prefilter ATTR_UNIT_OF_MEASUREMENT as its much faster in sql."""
    return ~StateAttributes.shared_attrs.like(
        UNIT_OF_MEASUREMENT_JSON_LIKE
    ) | ~States.attributes.like(UNIT_OF_MEASUREMENT_JSON_LIKE)


def apply_states_context_hints(sel: Select) -> Select:
    """Force mysql to use the right index on large context_id selects."""
    return sel.with_hint(
        States, f"FORCE INDEX ({STATES_CONTEXT_ID_INDEX})", dialect_name="mysql"
    )


def apply_events_context_hints(sel: Select) -> Select:
    """Force mysql to use the right index on large context_id selects."""
    return sel.with_hint(
        Events, f"FORCE INDEX ({EVENTS_CONTEXT_ID_INDEX})", dialect_name="mysql"
    )
