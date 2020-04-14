"""Test debug things."""
import pytest

from homeassistant import debug


async def test_raise_in_loop_async():
    """Test raise_in_loop raises when called from event loop."""
    with pytest.raises(RuntimeError):
        debug.raise_in_loop()


def test_raise_in_loop_sync():
    """Test raise_in_loop not raises when called from thread."""
    debug.raise_in_loop()


async def test_protect_loop_async():
    """Test protect_loop raises when called from event loop."""
    with pytest.raises(RuntimeError):
        debug.protect_loop(lambda: None)()


def test_protect_loop_sync():
    """Test protect_loop not raises when called from thread."""
    debug.protect_loop(lambda: None)()
