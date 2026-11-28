"""Test certificate monitoring against a local TLS server."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path
import ssl
from unittest.mock import Mock, patch

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
import pytest_socket

from homeassistant.components.cert_expiry.const import CONF_CA_CERTIFICATES, DOMAIN
from homeassistant.components.cert_expiry.errors import ValidationFailure
from homeassistant.components.cert_expiry.helper import (
    async_get_ssl_context,
    get_cert_expiry_timestamp,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VERIFY_SSL, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util.dt import utcnow
from homeassistant.util.ssl import create_client_context, get_default_context

pytestmark = pytest.mark.usefixtures("socket_enabled")

# Python's ssl module does not expose OpenSSL's verification code constants.
X509_V_ERR_CERT_NOT_YET_VALID = 9
X509_V_ERR_CERT_HAS_EXPIRED = 10
X509_V_ERR_DEPTH_ZERO_SELF_SIGNED_CERT = 18
X509_V_ERR_IP_ADDRESS_MISMATCH = 64


@pytest.fixture(autouse=True)
def allow_loopback() -> None:
    """Permit both loopback addresses used by localhost and Happy Eyeballs."""
    pytest_socket.socket_allow_hosts(["127.0.0.1", "::1"])


@pytest.fixture
async def ignore_tls_client_abort(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Allow the local server's expected reset when the client rejects its cert."""
    original_handler = hass.loop.get_exception_handler()
    assert original_handler is not None

    def handle_exception(
        loop: asyncio.AbstractEventLoop, context: dict[str, object]
    ) -> None:
        if (
            isinstance(context.get("exception"), ConnectionResetError)
            and context.get("message")
            == "Error on transport creation for incoming connection"
        ):
            return
        original_handler(loop, context)

    hass.loop.set_exception_handler(handle_exception)
    try:
        yield
        await hass.async_block_till_done()
    finally:
        hass.loop.set_exception_handler(original_handler)


@pytest.fixture
def server_context(
    tmp_path: Path,
    certificate_key: ec.EllipticCurvePrivateKey,
    certificate_pem: str,
    request: pytest.FixtureRequest,
) -> ssl.SSLContext:
    """Load the test server's certificate and private key."""
    cert_path = tmp_path / "certificate.pem"
    key_path = tmp_path / "key.pem"
    if hasattr(request, "param"):
        certificate_pem = request.getfixturevalue(request.param)
    cert_path.write_text(certificate_pem, encoding="ascii")
    key_path.write_bytes(
        certificate_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    return context


@pytest.fixture
async def tls_port(
    hass: HomeAssistant, server_context: ssl.SSLContext
) -> AsyncGenerator[int]:
    """Serve TLS on an ephemeral loopback port."""
    server = await hass.loop.create_server(
        asyncio.Protocol, "127.0.0.1", 0, ssl=server_context
    )
    async with server:
        yield server.sockets[0].getsockname()[1]


@pytest.fixture
def trusted_context(certificate: x509.Certificate) -> ssl.SSLContext:
    """Trust the local certificate without modifying shared contexts."""
    context = create_client_context()
    context.load_verify_locations(
        cadata=certificate.public_bytes(serialization.Encoding.PEM).decode("ascii")
    )
    return context


@pytest.mark.parametrize(
    "certificate_dates",
    [
        pytest.param(
            (datetime(2020, 1, 1, tzinfo=UTC), datetime(2100, 1, 1, tzinfo=UTC)),
            id="self-signed",
        ),
        pytest.param(
            (datetime(2010, 1, 1, tzinfo=UTC), datetime(2020, 1, 1, tzinfo=UTC)),
            id="expired",
        ),
        pytest.param(
            (datetime(2090, 1, 1, tzinfo=UTC), datetime(2100, 1, 1, tzinfo=UTC)),
            id="not-yet-valid",
        ),
    ],
)
async def test_unverified_tls_sensor(
    hass: HomeAssistant,
    certificate: x509.Certificate,
    tls_port: int,
    server_context: ssl.SSLContext,
) -> None:
    """Monitor presented certificates even when their trust or dates are invalid."""
    sni_callback = Mock(return_value=None)
    server_context.set_servername_callback(sni_callback)
    shared_context = get_default_context()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "localhost", CONF_PORT: tls_port, CONF_VERIFY_SSL: False},
        unique_id=f"localhost:{tls_port}",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.localhost_{tls_port}_cert_expiry")
    assert state is not None
    assert state.state == certificate.not_valid_after_utc.isoformat()
    assert state.attributes["is_valid"] is False
    assert state.attributes["error"] is None
    assert sni_callback.call_args.args[1] == "localhost"
    assert get_default_context() is shared_context
    assert shared_context.check_hostname
    assert shared_context.verify_mode == ssl.CERT_REQUIRED


@pytest.mark.parametrize(
    "server_context",
    [pytest.param("unsupported_certificate_pem", id="unsupported-version")],
    indirect=True,
)
async def test_unverified_tls_unsupported_version(
    hass: HomeAssistant, tls_port: int
) -> None:
    """Keep an unsupported peer certificate available with a validation error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "localhost", CONF_PORT: tls_port, CONF_VERIFY_SSL: False},
        unique_id=f"localhost:{tls_port}",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.localhost_{tls_port}_cert_expiry")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["is_valid"] is False
    assert state.attributes["error"] == (
        f"Invalid certificate received from: localhost:{tls_port}"
    )


@pytest.mark.usefixtures("ignore_tls_client_abort")
async def test_untrusted_tls_certificate(hass: HomeAssistant, tls_port: int) -> None:
    """Default verification rejects a self-signed certificate."""
    with pytest.raises(ValidationFailure) as exc:
        await get_cert_expiry_timestamp(hass, "localhost", tls_port)

    cause = exc.value.__cause__
    assert isinstance(cause, ssl.SSLCertVerificationError)
    assert cause.verify_code == X509_V_ERR_DEPTH_ZERO_SELF_SIGNED_CERT


async def test_trusted_tls_certificate(
    hass: HomeAssistant,
    tls_port: int,
    certificate: x509.Certificate,
    trusted_context: ssl.SSLContext,
) -> None:
    """Verification still retrieves the expiry of a trusted certificate."""
    with patch(
        "homeassistant.components.cert_expiry.helper.get_default_context",
        return_value=trusted_context,
    ):
        assert (
            await get_cert_expiry_timestamp(hass, "localhost", tls_port)
            == certificate.not_valid_after_utc
        )


@pytest.mark.parametrize(
    ("certificate_dates", "verify_code"),
    [
        pytest.param(
            (datetime(2010, 1, 1, tzinfo=UTC), datetime(2020, 1, 1, tzinfo=UTC)),
            X509_V_ERR_CERT_HAS_EXPIRED,
            id="expired",
        ),
        pytest.param(
            (datetime(2090, 1, 1, tzinfo=UTC), datetime(2100, 1, 1, tzinfo=UTC)),
            X509_V_ERR_CERT_NOT_YET_VALID,
            id="not-yet-valid",
        ),
    ],
)
@pytest.mark.usefixtures("ignore_tls_client_abort")
async def test_verified_tls_invalid_dates(
    hass: HomeAssistant,
    tls_port: int,
    trusted_context: ssl.SSLContext,
    verify_code: int,
) -> None:
    """Trusting a certificate still enforces its validity period."""
    with (
        patch(
            "homeassistant.components.cert_expiry.helper.get_default_context",
            return_value=trusted_context,
        ),
        pytest.raises(ValidationFailure) as exc,
    ):
        await get_cert_expiry_timestamp(hass, "localhost", tls_port)

    cause = exc.value.__cause__
    assert isinstance(cause, ssl.SSLCertVerificationError)
    assert cause.verify_code == verify_code


@pytest.mark.usefixtures("ignore_tls_client_abort")
async def test_tls_hostname_mismatch(
    hass: HomeAssistant, tls_port: int, trusted_context: ssl.SSLContext
) -> None:
    """Trusting a certificate does not disable hostname verification."""
    with (
        patch(
            "homeassistant.components.cert_expiry.helper.get_default_context",
            return_value=trusted_context,
        ),
        pytest.raises(ValidationFailure) as exc,
    ):
        await get_cert_expiry_timestamp(hass, "127.0.0.1", tls_port)

    cause = exc.value.__cause__
    assert isinstance(cause, ssl.SSLCertVerificationError)
    assert cause.verify_code == X509_V_ERR_IP_ADDRESS_MISMATCH


@pytest.mark.parametrize("certificate", ["private-ca"], indirect=True)
async def test_private_ca_tls_sensor(
    hass: HomeAssistant,
    certificate: x509.Certificate,
    ca_certificate: x509.Certificate,
    tls_port: int,
) -> None:
    """Verify a real CA-issued certificate using only the entry's extra trust."""
    shared_certificates = get_default_context().get_ca_certs(binary_form=True)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "localhost",
            CONF_PORT: tls_port,
            CONF_VERIFY_SSL: True,
            CONF_CA_CERTIFICATES: ca_certificate.public_bytes(
                serialization.Encoding.PEM
            ).decode("ascii"),
        },
        unique_id=f"localhost:{tls_port}",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.localhost_{tls_port}_cert_expiry")
    assert state is not None
    assert state.state == certificate.not_valid_after_utc.isoformat()
    assert state.attributes["is_valid"] is True
    assert state.attributes["error"] is None
    assert get_default_context().get_ca_certs(binary_form=True) == shared_certificates


@pytest.mark.parametrize(
    ("initial_verification", "initial_bundle"),
    [
        pytest.param(False, "empty", id="enable-without-reload"),
        pytest.param(True, "issuer", id="disable-without-reload"),
    ],
)
@pytest.mark.parametrize(
    "certificate", [pytest.param("private-ca", id="private-ca")], indirect=True
)
@pytest.mark.freeze_time("2026-01-01")
async def test_entry_update_keeps_tls_verification(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    certificate: x509.Certificate,
    ca_certificate: x509.Certificate,
    tls_port: int,
    server_context: ssl.SSLContext,
    initial_verification: bool,
    initial_bundle: str,
) -> None:
    """Report the cached context's verification mode until the entry reloads."""
    sni_callback = Mock(return_value=None)
    server_context.set_servername_callback(sni_callback)
    bundles = {
        "empty": "",
        "issuer": ca_certificate.public_bytes(serialization.Encoding.PEM).decode(
            "ascii"
        ),
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "localhost",
            CONF_PORT: tls_port,
            CONF_VERIFY_SSL: initial_verification,
            CONF_CA_CERTIFICATES: bundles[initial_bundle],
        },
        unique_id=f"localhost:{tls_port}",
    )
    entry.add_to_hass(hass)
    entity_id = f"sensor.localhost_{tls_port}_cert_expiry"

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data
    initial_handshakes = sni_callback.call_count
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == certificate.not_valid_after_utc.isoformat()
    assert state.attributes["is_valid"] is initial_verification

    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_VERIFY_SSL: not initial_verification}
    )
    freezer.tick(timedelta(hours=12))
    async_fire_time_changed(hass, utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.runtime_data is coordinator
    assert sni_callback.call_count == initial_handshakes + 1
    assert sni_callback.call_args.args[1] == "localhost"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == certificate.not_valid_after_utc.isoformat()
    assert state.attributes["is_valid"] is initial_verification
    assert state.attributes["error"] is None


@pytest.mark.parametrize("certificate", ["private-ca"], indirect=True)
@pytest.mark.usefixtures("ignore_tls_client_abort")
async def test_private_ca_hostname_mismatch(
    hass: HomeAssistant, ca_certificate: x509.Certificate, tls_port: int
) -> None:
    """Additional CA trust does not weaken hostname validation."""
    context = await async_get_ssl_context(
        hass,
        ca_certificates=ca_certificate.public_bytes(serialization.Encoding.PEM).decode(
            "ascii"
        ),
    )
    with pytest.raises(ValidationFailure) as exc:
        await get_cert_expiry_timestamp(
            hass, "127.0.0.1", tls_port, ssl_context=context
        )

    cause = exc.value.__cause__
    assert isinstance(cause, ssl.SSLCertVerificationError)
    assert cause.verify_code == X509_V_ERR_IP_ADDRESS_MISMATCH


@pytest.mark.parametrize(
    (
        "certificate",
        "initial_settings",
        "updated_settings",
        "initial_result",
        "expected_result",
    ),
    [
        pytest.param(
            "self-signed",
            (True, "empty"),
            (False, "empty"),
            (STATE_UNKNOWN, False, False),
            ("timestamp", False, True),
            id="disable-verification",
        ),
        pytest.param(
            "self-signed",
            (False, "empty"),
            (True, "empty"),
            ("timestamp", False, True),
            (STATE_UNKNOWN, False, False),
            id="enable-verification",
        ),
        pytest.param(
            "private-ca",
            (False, "issuer"),
            (True, "issuer"),
            ("timestamp", False, True),
            ("timestamp", True, True),
            id="enable-verification-same-expiry",
        ),
        pytest.param(
            "private-ca",
            (True, "issuer"),
            (False, "issuer"),
            ("timestamp", True, True),
            ("timestamp", False, True),
            id="disable-verification-same-expiry",
        ),
        pytest.param(
            "private-ca",
            (True, "empty"),
            (True, "issuer"),
            (STATE_UNKNOWN, False, False),
            ("timestamp", True, True),
            id="add-ca",
        ),
        pytest.param(
            "private-ca",
            (True, "unrelated"),
            (True, "issuer"),
            (STATE_UNKNOWN, False, False),
            ("timestamp", True, True),
            id="replace-with-issuer",
        ),
        pytest.param(
            "private-ca",
            (True, "issuer"),
            (True, "unrelated"),
            ("timestamp", True, True),
            (STATE_UNKNOWN, False, False),
            id="replace-with-unrelated",
        ),
        pytest.param(
            "private-ca",
            (True, "issuer"),
            (True, "empty"),
            ("timestamp", True, True),
            (STATE_UNKNOWN, False, False),
            id="clear-ca",
        ),
        pytest.param(
            "private-ca",
            (True, "issuer"),
            (True, "whitespace"),
            ("timestamp", True, True),
            (STATE_UNKNOWN, False, False),
            id="clear-ca-with-whitespace",
        ),
    ],
    indirect=["certificate"],
)
@pytest.mark.usefixtures("ignore_tls_client_abort")
async def test_reconfigure_tls_settings(
    hass: HomeAssistant,
    certificate: x509.Certificate,
    ca_certificate: x509.Certificate,
    unrelated_ca_certificate: x509.Certificate,
    tls_port: int,
    initial_settings: tuple[bool, str],
    updated_settings: tuple[bool, str],
    initial_result: tuple[str, bool, bool],
    expected_result: tuple[str, bool, bool],
) -> None:
    """Apply TLS settings through the public reconfigure flow and reload."""
    initial_verification, initial_bundle = initial_settings
    verify_ssl, new_bundle = updated_settings
    initial_state, initial_valid, initial_error_is_none = initial_result
    expected_state, expected_valid, expected_error_is_none = expected_result
    bundles = {
        "empty": "",
        "whitespace": " \n\t ",
        "issuer": ca_certificate.public_bytes(serialization.Encoding.PEM).decode(
            "ascii"
        ),
        "unrelated": unrelated_ca_certificate.public_bytes(
            serialization.Encoding.PEM
        ).decode("ascii"),
    }
    expected_states = {
        "timestamp": certificate.not_valid_after_utc.isoformat(),
        STATE_UNKNOWN: STATE_UNKNOWN,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "localhost",
            CONF_PORT: tls_port,
            CONF_VERIFY_SSL: initial_verification,
            CONF_CA_CERTIFICATES: bundles[initial_bundle],
        },
        unique_id=f"localhost:{tls_port}",
    )
    entry.add_to_hass(hass)
    entry_id = entry.entry_id
    entity_id = f"sensor.localhost_{tls_port}_cert_expiry"

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_states[initial_state]
    assert state.attributes["is_valid"] is initial_valid
    assert (state.attributes["error"] is None) is initial_error_is_none

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "localhost",
            CONF_PORT: tls_port,
            CONF_VERIFY_SSL: verify_ssl,
            CONF_CA_CERTIFICATES: bundles[new_bundle],
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not coordinator
    assert entry.entry_id == entry_id
    assert entry.unique_id == f"localhost:{tls_port}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_states[expected_state]
    assert state.attributes["is_valid"] is expected_valid
    assert (state.attributes["error"] is None) is expected_error_is_none
