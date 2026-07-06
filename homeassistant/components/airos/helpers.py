"""Helpers for airOS."""

import ssl


def build_legacy_context(*, verify_ssl: bool) -> ssl.SSLContext:
    """Build an SSL context compatible with legacy airOS 6 devices."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
    ctx.minimum_version = ssl.TLSVersion.TLSv1

    if not verify_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    return ctx
