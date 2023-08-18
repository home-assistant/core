"""Tests for audio ring buffer."""
from homeassistant.components.assist_pipeline.ring_buffer import RingBuffer


def test_ring_buffer_empty() -> None:
    """Test empty ring buffer."""
    rb = RingBuffer(10)
    assert rb.maxlen == 10
    assert rb.pos == 0
    assert rb.getvalue() == b""


def test_ring_buffer_put_1() -> None:
    """Test putting some data smaller than the maximum length."""
    rb = RingBuffer(10)
    rb.put(bytes([1, 2, 3, 4, 5]))
    assert rb.pos == 5
    assert rb.getvalue() == bytes([1, 2, 3, 4, 5])


def test_ring_buffer_put_2() -> None:
    """Test putting some data past the end of the buffer."""
    rb = RingBuffer(10)
    rb.put(bytes([1, 2, 3, 4, 5]))
    rb.put(bytes([6, 7, 8, 9, 10, 11, 12]))
    assert rb.pos == 2
    assert rb.getvalue() == bytes([3, 4, 5, 6, 7, 8, 9, 10, 11, 12])


def test_ring_buffer_put_too_large() -> None:
    """Test putting data too large for the buffer."""
    rb = RingBuffer(10)
    rb.put(bytes([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]))
    assert rb.pos == 2
    assert rb.getvalue() == bytes([3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
