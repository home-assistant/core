"""Helper functions for the Cert Expiry platform."""

import datetime
from ipaddress import ip_address
import logging
import socket
import ssl

import certifi.core
from cryptography.x509 import (
    Certificate,
    DNSName,
    ExtensionNotFound,
    IPAddress,
    SubjectAlternativeName,
)
from cryptography.x509.oid import ExtensionOID, NameOID
from OpenSSL import SSL
from OpenSSL.crypto import (
    FILETYPE_ASN1,
    X509,
    X509Store,
    X509StoreContext,
    X509StoreContextError,
    load_certificate,
)

from homeassistant.core import HomeAssistant
from homeassistant.util.ssl import get_default_context

from .errors import (
    ConnectionRefused,
    ConnectionReset,
    ConnectionTimeout,
    ValidationFailure,
)

_LOGGER = logging.getLogger(__name__)


def _build_system_ca_store(store: X509Store):
    ssl_context = get_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.verify_flags = ssl_context.verify_flags | ssl.VERIFY_CRL_CHECK_CHAIN

    system_certs_count = 0
    for sys_cert_der in ssl_context.get_ca_certs(binary_form=True):
        try:
            # Load the system cert into pyOpenSSL format
            ca_cert = load_certificate(FILETYPE_ASN1, sys_cert_der)
            store.add_cert(ca_cert)
            system_certs_count += 1
        except Exception:  # noqa: BLE001
            # Skip invalid system certificate
            continue

    # fallback: If certificates can't be found using SSLContext, use certifi
    if system_certs_count == 0:
        _LOGGER.warning("System store returned 0 certs. Falling back to certifi.")
        store.load_locations(certifi.where())


def _check_name(pattern: str, hostname: str) -> bool:
    """Basic wildcard matching logic."""
    if pattern == hostname:
        return True

    # Handle wildcards (e.g., *.google.com)
    if pattern.startswith("*.") and len(pattern) > 2:
        suffix = pattern[2:]
        # Check if hostname ends with suffix and has no more dots in the prefix
        if hostname.endswith(suffix):
            prefix = hostname[: -len(suffix)]
            # Wildcards match one label only (e.g. *.example.com does not match a.b.example.com)
            if prefix and prefix[-1] == "." and prefix.count(".") == 1:
                return True
    return False


def _match_hostname(cert: Certificate, hostname: str) -> bool:
    """Checks if the hostname matches the certificate's SANs or Common Name.

    Supports basic wildcards (*.example.com) by checking whether the base is the same, and it's at the same level.
    """

    try:
        san_ext = cert.extensions.get_extension_for_oid(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        )
        # noinspection PyTypeChecker
        san_value: SubjectAlternativeName = san_ext.value
        san_names = san_value.get_values_for_type(DNSName)
        san_ips = san_value.get_values_for_type(IPAddress)

        for name in san_names:
            if _check_name(name, hostname):
                return True

        try:
            given_ip = ip_address(hostname)

            for ip in san_ips:
                if ip == given_ip:
                    return True
        except ValueError:
            pass

        # If SANs exist, skip CN check.
        if san_names:
            return False

    except ExtensionNotFound:
        # If no SANs are present, fall through to Common Name
        pass

    common_names = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    for cn in common_names:  # noqa: SIM110, else it's less readable
        if _check_name(cn.value, hostname):
            return True

    # Nothing matches
    return False


SYSTEM_CA_STORE = X509Store()
_build_system_ca_store(SYSTEM_CA_STORE)


def verify_cert(cert: Certificate, peer_certs: list[Certificate], hostname: str):
    """Verifies the certificate against the system store."""

    openssl_cert = X509.from_cryptography(cert)
    openssl_peer_certs = [X509.from_cryptography(peer_cert) for peer_cert in peer_certs]

    verify_context = X509StoreContext(SYSTEM_CA_STORE, openssl_cert, openssl_peer_certs)
    try:
        verify_context.verify_certificate()
    except X509StoreContextError as err:
        raise ValidationFailure(err.args[0]) from err

    if not _match_hostname(cert, hostname):
        raise ValidationFailure(f"The certificate hostname doesn't match {hostname}")


def _get_cert_sync(
    hostname: str,
    port: int,
) -> tuple[Certificate, list[Certificate]]:
    """Get the certificate for the host and port combination."""

    try:
        context = SSL.Context(method=SSL.TLS_METHOD)
        _build_system_ca_store(context.get_cert_store())

        conn = SSL.Connection(
            context, socket=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        )
        conn.settimeout(5)
        conn.set_tlsext_host_name(hostname.encode())
        conn.setblocking(1)
        try:
            conn.connect((hostname, port))
            conn.do_handshake()
            cert = conn.get_peer_certificate(as_cryptography=True)
            peer_certs = conn.get_peer_cert_chain(as_cryptography=True)
        finally:
            conn.close()

    except TimeoutError as err:
        raise ConnectionTimeout(
            f"Connection timeout with server: {hostname}:{port}"
        ) from err
    except ConnectionRefusedError as err:
        raise ConnectionRefused(
            f"Connection refused by server: {hostname}:{port}"
        ) from err
    except ConnectionResetError as err:
        raise ConnectionReset(f"Connection reset by server: {hostname}:{port}") from err
    except ssl.CertificateError as err:
        raise ValidationFailure(err.verify_message) from err
    except ssl.SSLError as err:
        raise ValidationFailure(err.args[0]) from err

    if cert is None:
        raise ValidationFailure(
            f"No certificate received from server: {hostname}:{port}"
        )

    return cert, peer_certs


async def get_cert(
    hass: HomeAssistant,
    host: str,
    port: int,
) -> tuple[Certificate, list[Certificate]]:
    """Get the certificate for the host and port combination."""

    return await hass.async_add_executor_job(
        _get_cert_sync,
        host,
        port,
    )


def get_cert_expiry_timestamp(
    cert: Certificate | None,
    hostname: str,
    port: int,
) -> datetime.datetime:
    """Return the certificate's expiration timestamp."""
    not_after = cert.not_valid_after_utc
    if not_after is None:
        raise ValidationFailure(
            f"No expiry date in certificate from server: {hostname}:{port}"
        )
    return not_after
