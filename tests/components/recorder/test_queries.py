"""Tests for the recorder queries."""

import pytest
from sqlalchemy import update

from homeassistant.components.recorder.db_schema import (
    EventData,
    Events,
    StateAttributes,
    States,
    StatesMeta,
)
from homeassistant.components.recorder.queries import (
    attributes_ids_exist_in_states,
    attributes_ids_exist_in_states_with_fast_in_distinct,
    data_ids_exist_in_events,
    data_ids_exist_in_events_with_fast_in_distinct,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant

# The subquery variants are used where a range scan is slow, currently
# PostgreSQL and older MariaDB. The distinct variants are used elsewhere. Both
# answer the same question and have to agree.
TIMESTAMPS = [
    pytest.param([1700000000.0], id="one_row"),
    pytest.param([None], id="one_row_without_timestamp"),
    pytest.param([1700000000.0, None], id="timestamp_first"),
    pytest.param([None, 1700000000.0], id="missing_timestamp_first"),
]


@pytest.mark.parametrize("timestamps", TIMESTAMPS)
@pytest.mark.usefixtures("recorder_mock")
async def test_data_ids_still_referenced_by_events(
    hass: HomeAssistant, timestamps: list[float | None]
) -> None:
    """Test a data_id that events still point at is never reported as unused."""
    with session_scope(hass=hass) as session:
        data = EventData(hash=1234, shared_data='{"key": "value"}')
        session.add(data)
        session.flush()
        data_id = data.data_id
        for time_fired_ts in timestamps:
            session.add(Events(data_id=data_id, time_fired_ts=time_fired_ts))
        session.flush()

        for query in (
            data_ids_exist_in_events,
            data_ids_exist_in_events_with_fast_in_distinct,
        ):
            found = [row[0] for row in session.execute(query([data_id])).all()]
            assert found == [data_id], f"{query.__name__} lost the reference"


@pytest.mark.parametrize("timestamps", TIMESTAMPS)
@pytest.mark.usefixtures("recorder_mock")
async def test_attributes_ids_still_referenced_by_states(
    hass: HomeAssistant, timestamps: list[float | None]
) -> None:
    """Test an attributes_id that states still point at is not reported unused."""
    with session_scope(hass=hass) as session:
        states_meta = StatesMeta(entity_id="sensor.test")
        attributes = StateAttributes(hash=1234, shared_attrs='{"key": "value"}')
        session.add_all([states_meta, attributes])
        session.flush()
        attributes_id = attributes.attributes_id
        for last_updated_ts in timestamps:
            state = States(
                metadata_id=states_meta.metadata_id,
                attributes_id=attributes_id,
                last_updated_ts=last_updated_ts,
            )
            session.add(state)
            session.flush()
            if last_updated_ts is None:
                # The column carries a default, so a row without a timestamp
                # cannot be inserted through the ORM. Databases predating the
                # timestamp migration do have them, which is what the backfill
                # in migration.py exists for.
                session.execute(
                    update(States)
                    .where(States.state_id == state.state_id)
                    .values(last_updated_ts=None)
                )

        for query in (
            attributes_ids_exist_in_states,
            attributes_ids_exist_in_states_with_fast_in_distinct,
        ):
            found = [row[0] for row in session.execute(query([attributes_id])).all()]
            assert found == [attributes_id], f"{query.__name__} lost the reference"
