"""Test Home Assistant shutdown util."""


from unittest.mock import Mock, patch

from homeassistant.util import shutdown


async def test_deadlock_safe_shutdown():
    """Test we can shutdown without deadlock."""

    normal_thread_mock = Mock(
        join=Mock(), daemon=False, is_alive=Mock(return_value=True)
    )
    dead_thread_mock = Mock(
        join=Mock(), daemon=False, is_alive=Mock(return_value=False)
    )
    daemon_thread_mock = Mock(
        join=Mock(), daemon=True, is_alive=Mock(return_value=True)
    )

    mock_threads = [normal_thread_mock, dead_thread_mock, daemon_thread_mock]

    with patch("homeassistant.util.threading.enumerate", return_value=mock_threads):
        shutdown.deadlock_safe_shutdown()

    assert normal_thread_mock.join.called
    assert not dead_thread_mock.join.called
    assert not daemon_thread_mock.join.called
