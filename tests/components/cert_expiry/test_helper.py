"""Tests for certificate retrieval and decoding."""

import asyncio
import ssl
from unittest.mock import Mock, patch

from cryptography import x509
import pytest

from homeassistant.components.cert_expiry.errors import (
    ConnectionTimeout,
    ValidationFailure,
)
from homeassistant.components.cert_expiry.helper import (
    async_get_cert,
    get_cert_expiry_timestamp,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.ssl import get_default_context, get_default_no_verify_context

from .const import HOST, PORT


@pytest.mark.parametrize(
    ("tls_options", "context"),
    [
        pytest.param({}, get_default_context(), id="default"),
        pytest.param({"verify_ssl": True}, get_default_context(), id="verified"),
        pytest.param(
            {"verify_ssl": False}, get_default_no_verify_context(), id="unverified"
        ),
    ],
)
async def test_get_certificate(
    hass: HomeAssistant,
    certificate_der: bytes,
    tls_options: dict[str, bool],
    context: ssl.SSLContext,
) -> None:
    """Retrieve raw bytes with SNI and the selected, unmodified TLS context."""
    transport = Mock(spec=asyncio.Transport)
    ssl_object = Mock(spec=ssl.SSLObject)
    ssl_object.getpeercert.return_value = certificate_der
    transport.get_extra_info.return_value = ssl_object

    with patch.object(
        hass.loop, "create_connection", return_value=(transport, Mock())
    ) as create_connection:
        assert await async_get_cert(hass, HOST, PORT, **tls_options) == certificate_der

    create_connection.assert_awaited_once_with(
        asyncio.Protocol,
        HOST,
        PORT,
        ssl=context,
        happy_eyeballs_delay=0.25,
        server_hostname=HOST,
    )
    transport.get_extra_info.assert_called_once_with("ssl_object")
    ssl_object.getpeercert.assert_called_once_with(binary_form=True)
    transport.close.assert_called_once_with()
    assert get_default_context().check_hostname
    assert get_default_context().verify_mode == ssl.CERT_REQUIRED
    assert not get_default_no_verify_context().check_hostname
    assert get_default_no_verify_context().verify_mode == ssl.CERT_NONE


@pytest.mark.parametrize(
    "verify_ssl",
    [pytest.param(True, id="verified"), pytest.param(False, id="unverified")],
)
async def test_certificate_expiry(
    hass: HomeAssistant,
    certificate: x509.Certificate,
    certificate_der: bytes,
    verify_ssl: bool,
) -> None:
    """Decode the raw certificate into a timezone-aware expiry timestamp."""
    with patch(
        "homeassistant.components.cert_expiry.helper.async_get_cert",
        return_value=certificate_der,
    ) as get_cert:
        assert (
            await get_cert_expiry_timestamp(hass, HOST, PORT, verify_ssl=verify_ssl)
            == certificate.not_valid_after_utc
        )

    get_cert.assert_awaited_once_with(hass, HOST, PORT, verify_ssl=verify_ssl)


@pytest.mark.parametrize(
    ("certificate_data", "error"),
    [
        pytest.param(None, "No certificate expiration found", id="missing"),
        pytest.param(
            b"invalid certificate", "Invalid certificate received", id="invalid"
        ),
    ],
)
async def test_invalid_certificate(
    hass: HomeAssistant, certificate_data: bytes | None, error: str
) -> None:
    """Report missing and malformed certificates as validation failures."""
    with (
        patch(
            "homeassistant.components.cert_expiry.helper.async_get_cert",
            return_value=certificate_data,
        ),
        pytest.raises(ValidationFailure, match=error),
    ):
        await get_cert_expiry_timestamp(hass, HOST, PORT)


async def test_transport_closed_on_certificate_error(hass: HomeAssistant) -> None:
    """Close a successful TLS connection even when reading its certificate fails."""
    transport = Mock(spec=asyncio.Transport)
    ssl_object = Mock(spec=ssl.SSLObject)
    ssl_object.getpeercert.side_effect = ValueError("certificate unavailable")
    transport.get_extra_info.return_value = ssl_object

    with (
        patch.object(hass.loop, "create_connection", return_value=(transport, Mock())),
        pytest.raises(ValueError, match="certificate unavailable"),
    ):
        await async_get_cert(hass, HOST, PORT)

    transport.close.assert_called_once_with()


async def test_connection_timeout_cancels_handshake(hass: HomeAssistant) -> None:
    """Cancel a stalled connection rather than leaving its handshake running."""
    cancelled = asyncio.Event()

    async def stalled_connection(*_args: object, **_kwargs: object) -> None:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with (
        patch.object(hass.loop, "create_connection", side_effect=stalled_connection),
        patch("homeassistant.components.cert_expiry.helper.TIMEOUT", 0),
        pytest.raises(ConnectionTimeout),
    ):
        await get_cert_expiry_timestamp(hass, HOST, PORT)

    assert cancelled.is_set()
