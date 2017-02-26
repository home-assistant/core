"""Test util methods."""
from unittest.mock import patch, MagicMock

import pytest

from homeassistant.components.recorder import util

from .test_init import hass_recorder  # noqa


def test_recorder_bad_commit(hass_recorder):
    """Bad _commit should retry 3 times."""
    hass = hass_recorder()

    def work(session):
        """Bad work."""
        session.execute('select * from notthere')

    with patch('homeassistant.components.recorder.time.sleep') as e_mock, \
            util.session_scope(hass=hass) as session:
        res = util.commit(session, work)
    assert res is False
    assert e_mock.call_count == 3


def test_recorder_bad_execute(hass_recorder):
    """Bad execute, retry 3 times."""
    from sqlalchemy.exc import SQLAlchemyError
    hass = hass_recorder()

    def to_native():
        """Rasie exception."""
        raise SQLAlchemyError()

    mck1 = MagicMock()
    mck1.to_native = to_native

    with pytest.raises(SQLAlchemyError), \
            patch('homeassistant.components.recorder.time.sleep') as e_mock:
        util.execute(hass, (mck1,))

    assert e_mock.call_count == 2
