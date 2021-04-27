"""Test pool."""
import threading

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homeassistant.components.recorder.pool import RecorderPool


def test_recorder_pool():
    """Test RecorderPool gives the same connection in the creating thread."""

    engine = create_engine("sqlite://", poolclass=RecorderPool)
    get_session = sessionmaker(bind=engine)

    def _get_connection_twice():
        session = get_session()
        original_connection = session.connection().connection.connection
        session.close()

        session = get_session()
        second_connection = session.connection().connection.connection
        session.close()

        return original_connection, second_connection

    connections = _get_connection_twice()
    assert connections[0] == connections[1]

    def _test_in_new_thread():
        connections = _get_connection_twice()
        assert connections[0] != connections[1]

    new_thread = threading.Thread(target=_test_in_new_thread)
    new_thread.start()
    new_thread.join()
