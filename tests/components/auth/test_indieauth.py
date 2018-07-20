"""Tests for the client validator."""
from homeassistant.components.auth import indieauth

import pytest


def test_client_id_scheme():
    """Test we enforce valid scheme."""
    assert indieauth._parse_client_id('http://ex.com/')
    assert indieauth._parse_client_id('https://ex.com/')

    with pytest.raises(ValueError):
        indieauth._parse_client_id('ftp://ex.com')


def test_client_id_path():
    """Test we enforce valid path."""
    assert indieauth._parse_client_id('http://ex.com').path == '/'
    assert indieauth._parse_client_id('http://ex.com/hello').path == '/hello'
    assert indieauth._parse_client_id(
        'http://ex.com/hello/.world').path == '/hello/.world'
    assert indieauth._parse_client_id(
        'http://ex.com/hello./.world').path == '/hello./.world'

    with pytest.raises(ValueError):
        indieauth._parse_client_id('http://ex.com/.')

    with pytest.raises(ValueError):
        indieauth._parse_client_id('http://ex.com/hello/./yo')

    with pytest.raises(ValueError):
        indieauth._parse_client_id('http://ex.com/hello/../yo')


def test_client_id_fragment():
    """Test we enforce valid fragment."""
    with pytest.raises(ValueError):
        indieauth._parse_client_id('http://ex.com/#yoo')


def test_client_id_user_pass():
    """Test we enforce valid username/password."""
    with pytest.raises(ValueError):
        indieauth._parse_client_id('http://user@ex.com/')

    with pytest.raises(ValueError):
        indieauth._parse_client_id('http://user:pass@ex.com/')


def test_client_id_hostname():
    """Test we enforce valid hostname."""
    assert indieauth._parse_client_id('http://www.home-assistant.io/')
    assert indieauth._parse_client_id('http://[::1]')
    assert indieauth._parse_client_id('http://127.0.0.1')
    assert indieauth._parse_client_id('http://10.0.0.0')
    assert indieauth._parse_client_id('http://10.255.255.255')
    assert indieauth._parse_client_id('http://172.16.0.0')
    assert indieauth._parse_client_id('http://172.31.255.255')
    assert indieauth._parse_client_id('http://192.168.0.0')
    assert indieauth._parse_client_id('http://192.168.255.255')

    with pytest.raises(ValueError):
        assert indieauth._parse_client_id('http://255.255.255.255/')
    with pytest.raises(ValueError):
        assert indieauth._parse_client_id('http://11.0.0.0/')
    with pytest.raises(ValueError):
        assert indieauth._parse_client_id('http://172.32.0.0/')
    with pytest.raises(ValueError):
        assert indieauth._parse_client_id('http://192.167.0.0/')


def test_parse_url_lowercase_host():
    """Test we update empty paths."""
    assert indieauth._parse_url('http://ex.com/hello').path == '/hello'
    assert indieauth._parse_url('http://EX.COM/hello').hostname == 'ex.com'

    parts = indieauth._parse_url('http://EX.COM:123/HELLO')
    assert parts.netloc == 'ex.com:123'
    assert parts.path == '/HELLO'


def test_parse_url_path():
    """Test we update empty paths."""
    assert indieauth._parse_url('http://ex.com').path == '/'


def test_verify_redirect_uri():
    """Test that we verify redirect uri correctly."""
    assert indieauth.verify_redirect_uri(
        'http://ex.com',
        'http://ex.com/callback'
    )

    # Different domain
    assert not indieauth.verify_redirect_uri(
        'http://ex.com',
        'http://different.com/callback'
    )

    # Different scheme
    assert not indieauth.verify_redirect_uri(
        'http://ex.com',
        'https://ex.com/callback'
    )

    # Different subdomain
    assert not indieauth.verify_redirect_uri(
        'https://sub1.ex.com',
        'https://sub2.ex.com/callback'
    )
