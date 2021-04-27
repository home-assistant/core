"""Test pool."""
import threading

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homeassistant.components.recorder.pool import RecorderPool


def test_recorder_pool():
    """Test RecorderPool gives the same connection in the creating thread."""

    engine = create_engine("sqlite://", poolclass=RecorderPool)
    get_session = sessionmaker(bind=engine)

    connections = []

    def _get_connection_twice():
        session = get_session()
        connections.append(session.connection().connection.connection)
        session.close()

        session = get_session()
        connections.append(session.connection().connection.connection)
        session.close()

    _get_connection_twice()
    assert connections[0] == connections[1]

    new_thread = threading.Thread(target=_get_connection_twice)
    new_thread.start()
    new_thread.join()
    
    assert connections[2] != connections[3]
