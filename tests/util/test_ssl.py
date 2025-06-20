"""Test Home Assistant ssl utility functions."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.util.ssl import (
    SSLCipherList,
    client_context,
    create_client_context,
    create_no_verify_ssl_context,
)


@pytest.fixture
def mock_sslcontext():
    """Mock the ssl lib."""
    return MagicMock(set_ciphers=Mock(return_value=True))


def test_client_context(mock_sslcontext) -> None:
    """Test client context."""
    with patch("homeassistant.util.ssl.ssl.SSLContext", return_value=mock_sslcontext):
        client_context()
        mock_sslcontext.set_ciphers.assert_not_called()

        client_context(SSLCipherList.MODERN)
        mock_sslcontext.set_ciphers.assert_not_called()

        client_context(SSLCipherList.INTERMEDIATE)
        mock_sslcontext.set_ciphers.assert_not_called()

        client_context(SSLCipherList.INSECURE)
        mock_sslcontext.set_ciphers.assert_not_called()


def test_no_verify_ssl_context(mock_sslcontext) -> None:
    """Test no verify ssl context."""
    with patch("homeassistant.util.ssl.ssl.SSLContext", return_value=mock_sslcontext):
        create_no_verify_ssl_context()
        mock_sslcontext.set_ciphers.assert_not_called()

        create_no_verify_ssl_context(SSLCipherList.MODERN)
        mock_sslcontext.set_ciphers.assert_not_called()

        create_no_verify_ssl_context(SSLCipherList.INTERMEDIATE)
        mock_sslcontext.set_ciphers.assert_not_called()

        create_no_verify_ssl_context(SSLCipherList.INSECURE)
        mock_sslcontext.set_ciphers.assert_not_called()


def test_ssl_context_caching() -> None:
    """Test that SSLContext instances are cached correctly."""

    assert client_context() is client_context(SSLCipherList.PYTHON_DEFAULT)
    assert create_no_verify_ssl_context() is create_no_verify_ssl_context(
        SSLCipherList.PYTHON_DEFAULT
    )


def test_create_client_context(mock_sslcontext) -> None:
    """Test create client context."""
    with patch("homeassistant.util.ssl.ssl.SSLContext", return_value=mock_sslcontext):
        client_context()
        mock_sslcontext.set_ciphers.assert_not_called()

        client_context(SSLCipherList.MODERN)
        mock_sslcontext.set_ciphers.assert_not_called()

        client_context(SSLCipherList.INTERMEDIATE)
        mock_sslcontext.set_ciphers.assert_not_called()

        client_context(SSLCipherList.INSECURE)
        mock_sslcontext.set_ciphers.assert_not_called()


def test_create_client_context_independent() -> None:
    """Test create_client_context independence."""
    shared_context = client_context()
    independent_context_1 = create_client_context()
    independent_context_2 = create_client_context()
    assert shared_context is not independent_context_1
    assert independent_context_1 is not independent_context_2
