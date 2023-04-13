"""Test Home Assistant ssl utility functions."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.util.ssl import (
    SSL_CIPHER_LISTS,
    SslCipherList,
    client_context,
    create_no_verify_ssl_context,
)


@pytest.fixture
def mock_sslcontext():
    """Mock the ssl lib."""
    ssl_mock = MagicMock(set_ciphers=Mock(return_value=True))
    return ssl_mock


def test_client_context(mock_sslcontext) -> None:
    """Test client context."""
    with patch("homeassistant.util.ssl.ssl.SSLContext", return_value=mock_sslcontext):
        client_context()
        mock_sslcontext.set_ciphers.assert_not_called()

        client_context(SslCipherList.MODERN)
        mock_sslcontext.set_ciphers.assert_called_with(
            SSL_CIPHER_LISTS[SslCipherList.MODERN]
        )

        client_context(SslCipherList.INTERMEDIATE)
        mock_sslcontext.set_ciphers.assert_called_with(
            SSL_CIPHER_LISTS[SslCipherList.INTERMEDIATE]
        )


def test_no_verify_ssl_context(mock_sslcontext) -> None:
    """Test no verify ssl context."""
    with patch("homeassistant.util.ssl.ssl.SSLContext", return_value=mock_sslcontext):
        create_no_verify_ssl_context()
        mock_sslcontext.set_ciphers.assert_not_called()

        create_no_verify_ssl_context(SslCipherList.MODERN)
        mock_sslcontext.set_ciphers.assert_called_with(
            SSL_CIPHER_LISTS[SslCipherList.MODERN]
        )

        create_no_verify_ssl_context(SslCipherList.INTERMEDIATE)
        mock_sslcontext.set_ciphers.assert_called_with(
            SSL_CIPHER_LISTS[SslCipherList.INTERMEDIATE]
        )
