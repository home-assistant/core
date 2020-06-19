"""Test util methods."""
import pytest

from homeassistant.components.recorder import util
from homeassistant.components.recorder.const import DATA_INSTANCE

from tests.async_mock import MagicMock, patch
from tests.common import get_test_home_assistant, init_recorder_component


@pytest.fixture
def hass_recorder():
    """Home Assistant fixture with in-memory recorder."""
    hass = get_test_home_assistant()

    def setup_recorder(config=None):
        """Set up with params."""
        init_recorder_component(hass, config)
        hass.start()
        hass.block_till_done()
        hass.data[DATA_INSTANCE].block_till_done()
        return hass

    yield setup_recorder
    hass.stop()


def test_recorder_bad_commit(hass_recorder):
    """Bad _commit should retry 3 times."""
    hass = hass_recorder()

    def work(session):
        """Bad work."""
        session.execute("select * from notthere")

    with patch(
        "homeassistant.components.recorder.time.sleep"
    ) as e_mock, util.session_scope(hass=hass) as session:
        res = util.commit(session, work)
    assert res is False
    assert e_mock.call_count == 3


def test_recorder_bad_execute(hass_recorder):
    """Bad execute, retry 3 times."""
    from sqlalchemy.exc import SQLAlchemyError

    hass_recorder()

    def to_native(validate_entity_id=True):
        """Rasie exception."""
        raise SQLAlchemyError()

    mck1 = MagicMock()
    mck1.to_native = to_native

    with pytest.raises(SQLAlchemyError), patch(
        "homeassistant.components.recorder.time.sleep"
    ) as e_mock:
        util.execute((mck1,), to_native=True)

    assert e_mock.call_count == 2
