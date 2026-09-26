"""Helper functions for the Cert Expiry platform."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
import ipaddress
import socket
import ssl

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.x509 import Certificate, DNSName
from cryptography.x509.oid import NameOID
from cryptography.x509.verification import PolicyBuilder, Store, VerificationError
from propcache.api import cached_property

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util.ssl import (
    SSL_ALPN_HTTP11_HTTP2,
    SSLCipherList,
    client_context_no_verify,
)

from .const import TIMEOUT
from .errors import (
    ConnectionFailed,
    ConnectionRefused,
    ConnectionReset,
    ConnectionTimeout,
    HandshakeFailed,
    InvalidCertificate,
    NoCertificate,
    ResolveFailed,
)


@dataclass(frozen=True)
class HandshakeResult:
    """The peer certificate and the parameters negotiated in the TLS handshake."""

    cert: Certificate
    intermediates: list[Certificate]
    tls_version: str | None
    cipher_name: str | None
    cipher_protocol: str | None


def _first_attribute(name: x509.Name, oid: x509.ObjectIdentifier) -> str | None:
    """Return the first value of an RDN attribute, or None if it is absent."""
    attributes = name.get_attributes_for_oid(oid)
    return str(attributes[0].value) if attributes else None


@dataclass(frozen=True)
class CertificateInfo:
    """The fields of interest from a peer certificate."""

    serial_number: str
    version: str
    fingerprint: str
    not_valid_before: datetime
    not_valid_after: datetime
    common_name: str | None
    organization: str | None
    organizational_unit: str | None
    issuer_common_name: str | None
    issuer_organization: str | None

    @classmethod
    def from_certificate(cls, cert: Certificate) -> CertificateInfo:
        """Extract the fields of interest from a certificate."""
        return cls(
            serial_number=f"{cert.serial_number:X}",
            version=cert.version.name,
            fingerprint=cert.fingerprint(hashes.SHA256()).hex(":").upper(),
            not_valid_before=cert.not_valid_before_utc,
            not_valid_after=cert.not_valid_after_utc,
            common_name=_first_attribute(cert.subject, NameOID.COMMON_NAME),
            organization=_first_attribute(cert.subject, NameOID.ORGANIZATION_NAME),
            organizational_unit=_first_attribute(
                cert.subject, NameOID.ORGANIZATIONAL_UNIT_NAME
            ),
            issuer_common_name=_first_attribute(cert.issuer, NameOID.COMMON_NAME),
            issuer_organization=_first_attribute(
                cert.issuer, NameOID.ORGANIZATION_NAME
            ),
        )


async def async_get_cert(
    hass: HomeAssistant,
    host: str,
    port: int,
    timeout: float = TIMEOUT,
) -> HandshakeResult:
    """Connect to the host and port combination and return the handshake result."""
    transport: asyncio.Transport | None = None
    try:
        try:
            async with asyncio.timeout(timeout):
                transport, _ = await hass.loop.create_connection(
                    asyncio.Protocol,
                    host,
                    port,
                    ssl=client_context_no_verify(
                        SSLCipherList.INSECURE, SSL_ALPN_HTTP11_HTTP2
                    ),
                    happy_eyeballs_delay=0.25,
                    server_hostname=host,
                )
            ssl_object: ssl.SSLObject = transport.get_extra_info("ssl_object")
        finally:
            if transport is not None:
                transport.close()

        cert = ssl_object.getpeercert(binary_form=True)
        if not cert:
            raise NoCertificate(host, port)

        fullchain = [
            x509.load_der_x509_certificate(der)
            for der in ssl_object.get_unverified_chain()
        ]

        cipher_name, cipher_protocol, _ = ssl_object.cipher() or (None,) * 3
        return HandshakeResult(
            cert=fullchain[0],
            intermediates=fullchain[1:],
            tls_version=ssl_object.version(),
            cipher_name=cipher_name,
            cipher_protocol=cipher_protocol,
        )
    except socket.gaierror as err:
        raise ResolveFailed(host, port) from err
    except TimeoutError as err:
        raise ConnectionTimeout(host, port) from err
    except ConnectionRefusedError as err:
        raise ConnectionRefused(host, port) from err
    except ConnectionResetError as err:
        raise ConnectionReset(host, port) from err
    except ValueError as err:
        raise InvalidCertificate(host, port) from err
    except ssl.SSLError as err:
        raise HandshakeFailed(host, port, str(err)) from err
    except OSError as err:
        raise ConnectionFailed(host, port) from err


def _subject_name(host: str) -> DNSName | x509.IPAddress:
    """Return the verifier subject name for the host: an IP address or a DNS name."""
    try:
        return x509.IPAddress(ipaddress.ip_address(host))
    except ValueError:
        return DNSName(host)


class HandshakePolicyVerifier:
    """Checks a TLS handshake result against an SSLContext's policy for a host.

    The context's trust roots never change for a given context, so parsing
    them is cached on construction rather than repeated on every call. The
    built server verifier is not cached: its validation time is frozen at the
    moment it is built, so it must be rebuilt on every verify_cert() call or
    certificate expiry would stop being detected after that first build.
    """

    def __init__(self, context: ssl.SSLContext, host: str) -> None:
        """Store the context and host; defer parsing the trust roots until needed."""
        self._context = context
        self._subject = _subject_name(host)

    @cached_property
    def _policy_builder(self) -> PolicyBuilder:
        """Parse the context's trust roots once, since they never change for this context."""
        roots = [
            x509.load_der_x509_certificate(der)
            for der in self._context.get_ca_certs(binary_form=True)
        ]
        return PolicyBuilder().store(Store(roots))

    def verify_tls_version(self, tls_version: str | None) -> str | None:
        """Return why the TLS version is outside the context's range, or None if allowed."""
        min_version = self._context.minimum_version
        max_version = self._context.maximum_version
        if tls_version is None:
            return "No TLS version negotiated"
        try:
            version = ssl.TLSVersion[tls_version.replace(".", "_")]
        except KeyError:
            return f"Unrecognized TLS version: {tls_version}"
        if min_version != ssl.TLSVersion.MINIMUM_SUPPORTED and version < min_version:
            return f"{tls_version} is below the minimum TLS version"
        if max_version != ssl.TLSVersion.MAXIMUM_SUPPORTED and version > max_version:
            return f"{tls_version} is above the maximum TLS version"
        return None

    def verify_cipher(
        self, cipher_name: str | None, cipher_protocol: str | None
    ) -> str | None:
        """Return why the cipher is not allowed by the context, or None if allowed."""
        allowed = next(
            (c for c in self._context.get_ciphers() if c["name"] == cipher_name), None
        )
        if allowed is None:
            return f"Cipher {cipher_name} is not enabled"
        if allowed["protocol"] != cipher_protocol:
            return f"Cipher {cipher_name} uses {allowed['protocol']}, not {cipher_protocol}"

        # Not checking cipher bit strength because it is a part of the cipher, e.g. TLS_AES_256_GCM_SHA384

        return None

    def verify_cert(
        self, cert: x509.Certificate, intermediates: list[x509.Certificate]
    ) -> str | None:
        """Return the verification error for the host, or None if the cert is valid.

        The validation time is passed explicitly (rather than relying on
        build_server_verifier()'s implicit "now") so it is evaluated fresh on
        every call, matching dt_util.utcnow() consistently.
        """
        try:
            (
                self._policy_builder.time(dt_util.utcnow())
                .build_server_verifier(self._subject)
                .verify(cert, intermediates)
            )
        except (VerificationError, ValueError) as err:
            return str(err)
        return None
