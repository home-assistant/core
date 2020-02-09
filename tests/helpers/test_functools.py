"""Tests for HA functools."""

from homeassistant.core import callback, is_callback
from homeassistant.helpers import functools


def test_wraps_wrap_not_callback():
    """Test wraps function."""

    def to_wrap():
        pass

    to_wrap.hello = True

    @functools.wraps(to_wrap)
    def wrapped():
        pass

    assert wrapped.hello is True
    assert not is_callback(wrapped)

    @callback
    @functools.wraps(to_wrap)
    def wrapped():
        pass

    assert wrapped.hello is True
    assert is_callback(wrapped)

    @functools.wraps(to_wrap)
    @callback
    def wrapped():
        pass

    assert wrapped.hello is True
    assert is_callback(wrapped)


def test_wraps_callback():
    """Test wraps function."""

    @callback
    def to_wrap():
        pass

    to_wrap.hello = True

    @functools.wraps(to_wrap)
    def wrapped():
        pass

    assert wrapped.hello is True
    assert not is_callback(wrapped)

    @callback
    @functools.wraps(to_wrap)
    def wrapped():
        pass

    assert wrapped.hello is True
    assert is_callback(wrapped)

    @functools.wraps(to_wrap)
    @callback
    def wrapped():
        pass

    assert wrapped.hello is True
    assert is_callback(wrapped)
