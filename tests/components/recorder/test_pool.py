"""Test pool."""
import threading

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homeassistant.components.recorder.const import DB_WORKER_PREFIX
from homeassistant.components.recorder.pool import RecorderPool


def test_recorder_pool(caplog):
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
    assert "Database access is slower in the default executor" in caplog.text
    assert connections[0] != connections[1]

    caplog.clear()
    new_thread = threading.Thread(target=_get_connection_twice)
    new_thread.start()
    new_thread.join()
    assert "Database access is slower in the default executor" in caplog.text
    assert connections[2] != connections[3]

    caplog.clear()
    new_thread = threading.Thread(target=_get_connection_twice, name=DB_WORKER_PREFIX)
    new_thread.start()
    new_thread.join()
    assert "Database access is slower in the default executor" not in caplog.text
    assert connections[4] == connections[5]

    caplog.clear()
    new_thread = threading.Thread(target=_get_connection_twice, name="Recorder")
    new_thread.start()
    new_thread.join()
    assert "Database access is slower in the default executor" not in caplog.text
    assert connections[6] == connections[7]

    engine.pool.shutdown()
