"""Tests for airOS helpers."""

import ssl

from homeassistant.components.airos.helpers import build_legacy_context


def test_build_legacy_context() -> None:
    """Test building a legacy SSL context."""
    context = build_legacy_context(verify_ssl=False)

    assert isinstance(context, ssl.SSLContext)
    assert context.minimum_version == ssl.TLSVersion.TLSv1
    assert context.check_hostname is False
    assert context.verify_mode == ssl.CERT_NONE


def test_build_legacy_context_verify_ssl() -> None:
    """Test building a legacy SSL context with verification enabled."""
    context = build_legacy_context(verify_ssl=True)

    assert isinstance(context, ssl.SSLContext)
    assert context.minimum_version == ssl.TLSVersion.TLSv1
    assert context.check_hostname is True
