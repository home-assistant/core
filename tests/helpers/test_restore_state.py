"""The tests for the Restore component."""
# pylint: disable=protected-access
from datetime import timedelta
import logging

from homeassistant.bootstrap import setup_component
from homeassistant.core import split_entity_id, CoreState
from homeassistant.components import recorder, input_boolean
import homeassistant.util.dt as dt_util

from tests.common import (
    assert_setup_component, init_recorder_component, get_test_home_assistant)

_LOGGER = logging.getLogger(__name__)


def _add_test_data(entities):
    """Add test data before hass is started."""
    t_now = dt_util.utcnow() - timedelta(minutes=10)
    t_min_1 = t_now - timedelta(minutes=20)
    t_min_2 = t_now - timedelta(minutes=30)

    recorder_runs = recorder.get_model('RecorderRuns')
    states = recorder.get_model('States')
    with recorder.session_scope() as session:
        run = recorder_runs(
            start=t_min_2,
            end=t_now,
            created=t_min_2
        )
        recorder._INSTANCE._commit(session, run)

        for entity_id, state in entities.items():
            dbstate = states(
                entity_id=entity_id,
                domain=split_entity_id(entity_id)[0],
                state=state,
                attributes='{}',
                last_changed=t_min_1,
                last_updated=t_min_1,
                created=t_min_1)
            recorder._INSTANCE._commit(session, dbstate)


def test_restore_state():
    """Ensure states are 'restored' on startup."""
    test_entity_id1 = 'input_boolean.b1'
    test_entity_id2 = 'input_boolean.b2'
    test_entity_id3 = 'input_boolean.b3'

    def add_test_data():
        """Add test data to the DB."""
        _add_test_data({
            test_entity_id1: 'on',
            test_entity_id2: 'off',
            test_entity_id3: 'on',
        })

    hass = get_test_home_assistant()
    hass.state = CoreState.starting

    init_recorder_component(hass, db_ready_callback=add_test_data)
    hass.block_till_done()
    # recorder.get_instance()  # Wait for recorder to be ready

    with assert_setup_component(2):
        setup_component(hass, input_boolean.DOMAIN, {
            input_boolean.DOMAIN: {
                'b1': None,
                'b2': None,
            }})

    hass.block_till_done()
    hass.start()

    state = hass.states.get(test_entity_id1)
    assert state
    assert state.state == 'on'

    state = hass.states.get(test_entity_id2)
    assert state
    assert state.state == 'off'

    hass.stop()
