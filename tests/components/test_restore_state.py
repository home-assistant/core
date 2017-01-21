"""The tests for the Restore component."""
# pylint: disable=protected-access
from contextlib import contextmanager
from datetime import timedelta
import logging
from unittest.mock import patch

import pytest

from homeassistant.bootstrap import setup_component
from homeassistant.core import split_entity_id
from homeassistant.const import ATTR_RESTORED_STATE
from homeassistant.components import recorder
import homeassistant.components.recorder.models as models
from homeassistant.components import restore_state as restore
import homeassistant.util.dt as dt_util

from tests.common import assert_setup_component, get_test_home_assistant

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def hass_sql():
    """HASS fixture with in-memory recorder."""
    _hass = get_test_home_assistant()

    db_uri = 'sqlite://'  # In memory DB

    cnt_keys_in_config = 1
    with assert_setup_component(cnt_keys_in_config, recorder.DOMAIN):
        assert setup_component(_hass, recorder.DOMAIN, {
            recorder.DOMAIN: {
                recorder.CONF_DB_URL: db_uri,
            }})

    yield _hass
    _hass.stop()


@contextmanager
def patch_recorder_time(the_time, log_msg=None):
    """Patch the time for recorder and models.

    recording_start is set in the Recorder's init function
    """
    saved_time = recorder._INSTANCE.recording_start
    recorder._INSTANCE.recording_start = the_time
    with patch('homeassistant.components.recorder.dt_util.utcnow',
               return_value=the_time):
        _LOGGER.debug("Patched recorder time %s: %s", the_time, log_msg)
        yield
    recorder._INSTANCE.recording_start = saved_time


def _add_test_data(entities):
    """Add test data before hass is started."""
    t_now = dt_util.utcnow() - timedelta(minutes=10)
    t_min_1 = t_now - timedelta(minutes=20)
    t_min_2 = t_now - timedelta(minutes=30)

    recorder._INSTANCE._setup_connection()
    recorder._INSTANCE.block_till_db_ready()

    with patch_recorder_time(t_min_2, 'SETUP RUN'):
        recorder._INSTANCE._setup_run()

    with patch_recorder_time(t_min_1, 'COMMIT STATES'):
        for entity_id, state in entities.items():
            dbstate = models.States(
                entity_id=entity_id,
                domain=split_entity_id(entity_id)[0],
                state=state,
                last_changed=t_min_1,
                last_updated=t_min_1,
                created=t_min_1)
            recorder._INSTANCE._commit(dbstate)

    with patch_recorder_time(t_now, 'CLOSE RUN'):
        recorder._INSTANCE._close_run()


def test_restore_state(hass_sql):  # pylint: disable=redefined-outer-name
    """Ensure states are 'restored' on startup."""
    test_entity_id = 'sensor.temperature'
    test_entity_id2 = 'sensor.temperature2'
    _add_test_data({
        test_entity_id: 18,
        test_entity_id2: 20
    })

    hass_sql.block_till_done()

    with assert_setup_component(1, restore.DOMAIN):
        setup_component(hass_sql, restore.DOMAIN, {
            restore.DOMAIN: {
                restore.CONF_INCLUDE: {restore.CONF_ENTITIES: [test_entity_id]}
            }})

    # Start hass should load the state
    hass_sql.start()
    hass_sql.block_till_done()
    hass_sql.block_till_done()

    assert hass_sql.states.get(test_entity_id)
    assert hass_sql.states.get(test_entity_id).state == '18'
    assert hass_sql.states.get(test_entity_id).attributes[
        ATTR_RESTORED_STATE] is True

    # Ignored by config
    assert hass_sql.states.get(test_entity_id2) is None
