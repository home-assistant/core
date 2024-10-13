"""Test pool."""

import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homeassistant.components.recorder.const import DB_WORKER_PREFIX
from homeassistant.components.recorder.pool import RecorderPool


async def test_recorder_pool_called_from_event_loop() -> None:
    """Test we raise an exception when calling from the event loop."""
    recorder_and_worker_thread_ids: set[int] = set()
    engine = create_engine(
        "sqlite://",
        poolclass=RecorderPool,
        recorder_and_worker_thread_ids=recorder_and_worker_thread_ids,
    )
    with pytest.raises(RuntimeError):
        sessionmaker(bind=engine)().connection()


def test_recorder_pool(caplog: pytest.LogCaptureFixture) -> None:
    """Test RecorderPool gives the same connection in the creating thread."""
    recorder_and_worker_thread_ids: set[int] = set()
    engine = create_engine(
        "sqlite://",
        poolclass=RecorderPool,
        recorder_and_worker_thread_ids=recorder_and_worker_thread_ids,
    )
    get_session = sessionmaker(bind=engine)
    shutdown = False
    connections = []
    add_thread = False

    def _get_connection_twice():
        if add_thread:
            recorder_and_worker_thread_ids.add(threading.get_ident())
        session = get_session()
        connections.append(session.connection().connection.driver_connection)
        session.close()

        if shutdown:
            engine.pool.shutdown()

        session = get_session()
        connections.append(session.connection().connection.driver_connection)
        session.close()

    caplog.clear()
    new_thread = threading.Thread(target=_get_connection_twice)
    new_thread.start()
    new_thread.join()
    assert "accesses the database without the database executor" in caplog.text
    assert connections[0] != connections[1]

    add_thread = True
    caplog.clear()
    new_thread = threading.Thread(target=_get_connection_twice, name=DB_WORKER_PREFIX)
    new_thread.start()
    new_thread.join()
    assert "accesses the database without the database executor" not in caplog.text
    assert connections[2] == connections[3]

    caplog.clear()
    new_thread = threading.Thread(target=_get_connection_twice, name="Recorder")
    new_thread.start()
    new_thread.join()
    assert "accesses the database without the database executor" not in caplog.text
    assert connections[4] == connections[5]

    shutdown = True
    caplog.clear()
    new_thread = threading.Thread(target=_get_connection_twice, name=DB_WORKER_PREFIX)
    new_thread.start()
    new_thread.join()
    assert "accesses the database without the database executor" not in caplog.text
    assert connections[6] != connections[7]
