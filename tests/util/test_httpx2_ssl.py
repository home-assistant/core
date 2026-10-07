"""Test the certifi-backed default SSL context for httpx2."""

from collections.abc import Callable
from pathlib import Path
import ssl
from typing import Any
from unittest.mock import patch

import certifi
import httpcore2
import httpx2
import pytest
import truststore

from homeassistant.util.httpx2_ssl import CertifiSSLContext


def test_truststore_ssl_context_replaced() -> None:
    """Test truststore.SSLContext is replaced when importing Home Assistant."""
    assert truststore.SSLContext is CertifiSSLContext


DEFAULT_SSL_CONTEXT_FACTORIES = [
    pytest.param(httpx2.create_ssl_context, id="httpx2"),
    pytest.param(httpcore2.default_ssl_context, id="httpcore2"),
]


@pytest.fixture
def ca_bundle(tmp_path: Path) -> Path:
    """Return a CA bundle containing only the first certifi certificate."""
    certifi_bundle = Path(certifi.where()).read_text(encoding="utf-8")
    end_marker = "-----END CERTIFICATE-----"
    ca_bundle = tmp_path / "ca.pem"
    ca_bundle.write_text(
        certifi_bundle[: certifi_bundle.index(end_marker)] + end_marker,
        encoding="utf-8",
    )
    return ca_bundle


@pytest.mark.parametrize("create_context", DEFAULT_SSL_CONTEXT_FACTORIES)
def test_default_ssl_context_uses_certifi(
    monkeypatch: pytest.MonkeyPatch, create_context: Callable[[], ssl.SSLContext]
) -> None:
    """Test httpx2 default SSL contexts use certifi instead of truststore."""
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    expected = ssl.create_default_context(cafile=certifi.where())

    context = create_context()

    assert context.cert_store_stats() == expected.cert_store_stats()
    # truststore reloads the system CA store on every handshake
    with patch.object(ssl.SSLContext, "set_default_verify_paths") as mock_load:
        context.wrap_bio(ssl.MemoryBIO(), ssl.MemoryBIO(), server_hostname="a.b")
    mock_load.assert_not_called()


@pytest.mark.parametrize("create_context", DEFAULT_SSL_CONTEXT_FACTORIES)
def test_default_ssl_context_honors_ssl_cert_file(
    monkeypatch: pytest.MonkeyPatch,
    ca_bundle: Path,
    create_context: Callable[[], ssl.SSLContext],
) -> None:
    """Test httpx2 default SSL contexts still honor SSL_CERT_FILE."""
    monkeypatch.setenv("SSL_CERT_FILE", str(ca_bundle))

    assert create_context().cert_store_stats()["x509_ca"] == 1


def test_create_ssl_context_without_trust_env(
    monkeypatch: pytest.MonkeyPatch, ca_bundle: Path
) -> None:
    """Test CA environment variables are ignored when trust_env is False."""
    monkeypatch.setenv("SSL_CERT_FILE", str(ca_bundle))
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(ca_bundle))
    expected = ssl.create_default_context(cafile=certifi.where())

    context = httpx2.create_ssl_context(trust_env=False)

    assert context.cert_store_stats() == expected.cert_store_stats()


@pytest.mark.parametrize(
    "protocol",
    [
        pytest.param(ssl.PROTOCOL_TLS_CLIENT, id="client"),
        pytest.param(ssl.PROTOCOL_TLS_SERVER, id="server"),
    ],
)
def test_truststore_ssl_context_subclass(protocol: ssl._SSLMethod) -> None:
    """Test subclassing and isinstance checks on truststore.SSLContext work."""

    class CustomSSLContext(truststore.SSLContext):
        """Custom SSL context, as some libraries define."""

    expected = ssl.create_default_context(cafile=certifi.where())

    context = CustomSSLContext(protocol)

    assert isinstance(context, truststore.SSLContext)
    assert context.protocol == protocol
    assert context.cert_store_stats() == expected.cert_store_stats()
    assert context.verify_flags == expected.verify_flags


@pytest.mark.parametrize("create_context", DEFAULT_SSL_CONTEXT_FACTORIES)
def test_default_ssl_context_honors_sslkeylogfile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    create_context: Callable[[], ssl.SSLContext],
) -> None:
    """Test httpx2 default SSL contexts honor SSLKEYLOGFILE, like httpx did."""
    keylog_file = tmp_path / "keylog.txt"
    monkeypatch.setenv("SSLKEYLOGFILE", str(keylog_file))

    assert create_context().keylog_filename == str(keylog_file)


@pytest.mark.parametrize("create_context", DEFAULT_SSL_CONTEXT_FACTORIES)
def test_default_ssl_context_does_not_read_ca_bundle(
    monkeypatch: pytest.MonkeyPatch, create_context: Callable[[], ssl.SSLContext]
) -> None:
    """Test httpx2 default SSL contexts load CA certificates from memory."""
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)

    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    original_load = ssl.SSLContext.load_verify_locations

    def _load_verify_locations(self: ssl.SSLContext, *args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))
        original_load(self, *args, **kwargs)

    monkeypatch.setattr(ssl.SSLContext, "load_verify_locations", _load_verify_locations)

    create_context()

    # Only cadata is allowed by the blocking call detector
    assert len(calls) == 1
    assert calls[0][0] == ()
    assert calls[0][1].keys() == {"cadata"}
