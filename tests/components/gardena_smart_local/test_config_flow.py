"""Tests for the GARDENA smart local config flow."""

from collections.abc import Awaitable, Callable, Generator
from datetime import timedelta
import hashlib
from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.gardena_smart_local.config_flow import (
    _async_read_certificate,
    _async_try_connect,
    _GatewayCertificate,
)
from homeassistant.components.gardena_smart_local.const import (
    CONF_FINGERPRINT,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.components.gardena_smart_local.coordinator import (
    IncludableDeviceInfo,
)
from homeassistant.config_entries import (
    SOURCE_USER,
    SOURCE_ZEROCONF,
    ConfigFlowResult,
    ConfigSubentryData,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.util import dt as dt_util

MOCK_HOST = "192.168.1.100"
MOCK_PORT = DEFAULT_PORT
MOCK_PASSWORD = "testpassword"
MOCK_HOSTNAME = "GARDENA-123456"
MOCK_FINGERPRINT = "ab" * 32
OTHER_FINGERPRINT = "cd" * 32

PATCH_TRY_CONNECT = (
    "homeassistant.components.gardena_smart_local.config_flow._async_try_connect"
)
PATCH_READ_CERTIFICATE = (
    "homeassistant.components.gardena_smart_local.config_flow._async_read_certificate"
)
PATCH_SETUP_ENTRY = "homeassistant.components.gardena_smart_local.async_setup_entry"


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Prevent actual integration setup during config flow tests."""
    with patch(PATCH_SETUP_ENTRY, return_value=True):
        yield


@pytest.fixture(autouse=True)
def mock_read_certificate() -> Generator[MagicMock]:
    """Default to the certificate of a gateway on current firmware.

    Tests that need another certificate override this patch directly.
    """
    with patch(
        PATCH_READ_CERTIFICATE,
        return_value=_GatewayCertificate(MOCK_FINGERPRINT, MOCK_HOSTNAME),
    ) as read_certificate:
        yield read_certificate


def _make_zeroconf_info(
    hostname: str = "GARDENA-123456.local.",
    host: str = MOCK_HOST,
    port: int = MOCK_PORT,
) -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address=ip_address(host),
        ip_addresses=[ip_address(host)],
        hostname=hostname,
        name=f"{hostname.removesuffix('.')}._gardena-smart._tcp.local.",
        port=port,
        properties={},
        type="_gardena-smart._tcp.local.",
    )


async def _finish_flow(hass: HomeAssistant, flow_id: str) -> None:
    """Resubmit valid input to a user or discovery flow and finish it."""
    with patch(PATCH_TRY_CONNECT, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def _finish_reconfigure_flow(hass: HomeAssistant, flow_id: str) -> None:
    """Resubmit valid input to a reconfigure flow and finish it."""
    with patch(PATCH_TRY_CONNECT, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Happy path: manual entry creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(PATCH_TRY_CONNECT, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: MOCK_PORT,
        CONF_PASSWORD: MOCK_PASSWORD,
        CONF_FINGERPRINT: MOCK_FINGERPRINT,
    }
    assert result["result"].unique_id == MOCK_HOSTNAME
    assert result["result"].title == MOCK_HOSTNAME


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_strips_host_whitespace(hass: HomeAssistant) -> None:
    """Leading/trailing whitespace in the host is stripped before use."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(PATCH_TRY_CONNECT, return_value=None) as try_connect:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: f"  {MOCK_HOST}\t",
                CONF_PORT: MOCK_PORT,
                CONF_PASSWORD: MOCK_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_HOSTNAME
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert try_connect.call_args[0][1] == MOCK_HOST


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize("host", ["10.0.1.194 junk", "gateway\x00", "gate\nway", ""])
async def test_user_flow_invalid_host(
    hass: HomeAssistant, mock_read_certificate: MagicMock, host: str
) -> None:
    """A malformed host is rejected before any connection is attempted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: host, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}
    mock_read_certificate.assert_not_called()

    await _finish_flow(hass, result["flow_id"])


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_confirm_invalid_host(
    hass: HomeAssistant, mock_read_certificate: MagicMock
) -> None:
    """A malformed host in the discovery form is rejected before connecting."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_make_zeroconf_info()
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "bad host", CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}
    mock_read_certificate.assert_not_called()

    await _finish_flow(hass, result["flow_id"])


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_invalid_host(
    hass: HomeAssistant, mock_read_certificate: MagicMock
) -> None:
    """A malformed host in the reconfigure form is rejected before connecting."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HOSTNAME,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_FINGERPRINT: MOCK_FINGERPRINT,
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "bad host", CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}
    mock_read_certificate.assert_not_called()

    await _finish_reconfigure_flow(hass, result["flow_id"])


async def test_user_flow_rejects_out_of_range_port(hass: HomeAssistant) -> None:
    """A port outside 1-65535 fails schema validation, not a connection attempt."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: 70000, CONF_PASSWORD: MOCK_PASSWORD},
        )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Connection failure shows an error and keeps the form open."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "aiohttp.ClientSession.ws_connect",
        side_effect=aiohttp.ClientConnectionError("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    await _finish_flow(hass, result["flow_id"])


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_cert_unreachable(hass: HomeAssistant) -> None:
    """Without a readable certificate there is nothing to pin, so setup fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(PATCH_READ_CERTIFICATE, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    await _finish_flow(hass, result["flow_id"])


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Wrong password (HTTP 401) shows invalid_auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "aiohttp.ClientSession.ws_connect",
        side_effect=aiohttp.WSServerHandshakeError(
            request_info=MagicMock(),
            history=(),
            status=401,
            message="Unauthorized",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    await _finish_flow(hass, result["flow_id"])


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_unknown_error(hass: HomeAssistant) -> None:
    """Unexpected exception shows generic unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "aiohttp.ClientSession.ws_connect",
        side_effect=RuntimeError("Unexpected error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    await _finish_flow(hass, result["flow_id"])


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_handshake_error_non_401(hass: HomeAssistant) -> None:
    """A non-401 handshake error is reported as cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "aiohttp.ClientSession.ws_connect",
        side_effect=aiohttp.WSServerHandshakeError(
            request_info=MagicMock(),
            history=(),
            status=500,
            message="Internal Server Error",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    await _finish_flow(hass, result["flow_id"])


async def test_try_connect_success_closes_websocket(hass: HomeAssistant) -> None:
    """A successful probe closes the websocket and reports no error."""
    mock_ws = AsyncMock()
    mock_ws_cm = MagicMock()
    mock_ws_cm.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws_cm.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "aiohttp.ClientSession.ws_connect", return_value=mock_ws_cm
    ) as ws_connect:
        error = await _async_try_connect(
            hass, MOCK_HOST, MOCK_PORT, MOCK_PASSWORD, MOCK_FINGERPRINT
        )

    assert error is None
    ws_connect.assert_called_once()
    mock_ws.close.assert_awaited_once()


async def test_try_connect_pins_fingerprint(hass: HomeAssistant) -> None:
    """The probe only accepts the certificate with the given fingerprint."""
    mock_ws_cm = MagicMock()
    mock_ws_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_ws_cm.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "aiohttp.ClientSession.ws_connect", return_value=mock_ws_cm
    ) as ws_connect:
        await _async_try_connect(
            hass, MOCK_HOST, MOCK_PORT, MOCK_PASSWORD, MOCK_FINGERPRINT
        )

    pinned = ws_connect.call_args.kwargs["ssl"]
    assert isinstance(pinned, aiohttp.Fingerprint)
    assert pinned.fingerprint == bytes.fromhex(MOCK_FINGERPRINT)


async def test_try_connect_fingerprint_mismatch(hass: HomeAssistant) -> None:
    """A gateway presenting another certificate is reported as unreachable."""
    with patch(
        "aiohttp.ClientSession.ws_connect",
        side_effect=aiohttp.ServerFingerprintMismatch(
            bytes.fromhex(MOCK_FINGERPRINT), bytes.fromhex(OTHER_FINGERPRINT), "h", 1
        ),
    ):
        error = await _async_try_connect(
            hass, MOCK_HOST, MOCK_PORT, MOCK_PASSWORD, MOCK_FINGERPRINT
        )

    assert error == "cannot_connect"


def _make_certificate(*dns_names: str) -> bytes:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "gateway")])
    now = dt_util.utcnow()
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=1))
    )
    if dns_names:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(n) for n in dns_names]),
            critical=False,
        )
    return builder.sign(key, hashes.SHA256()).public_bytes(serialization.Encoding.DER)


def _mock_connection(der: bytes | None) -> tuple[MagicMock, AsyncMock]:
    writer = MagicMock()
    writer.wait_closed = AsyncMock()
    writer.get_extra_info.return_value = (
        MagicMock(getpeercert=MagicMock(return_value=der)) if der is not None else None
    )
    return writer, AsyncMock(return_value=(MagicMock(), writer))


@pytest.mark.parametrize(
    ("dns_names", "hostname"),
    [
        (("GARDENA-163008.local",), "GARDENA-163008"),
        (("other.example",), None),
        ((), None),
    ],
)
async def test_read_certificate(
    dns_names: tuple[str, ...], hostname: str | None
) -> None:
    """The fingerprint covers the whole certificate, the hostname comes from its SAN."""
    der = _make_certificate(*dns_names)
    writer, open_connection = _mock_connection(der)

    with patch("asyncio.open_connection", open_connection):
        certificate = await _async_read_certificate(MOCK_HOST, MOCK_PORT)

    assert certificate == _GatewayCertificate(hashlib.sha256(der).hexdigest(), hostname)
    writer.close.assert_called_once()


async def test_read_certificate_without_tls() -> None:
    """A connection without a TLS layer yields no certificate."""
    _, open_connection = _mock_connection(None)

    with patch("asyncio.open_connection", open_connection):
        assert await _async_read_certificate(MOCK_HOST, MOCK_PORT) is None


@pytest.mark.parametrize("error", [OSError, TimeoutError, ValueError])
async def test_read_certificate_unreachable(error: type[Exception]) -> None:
    """A connection error or malformed host yields no certificate."""
    with patch("asyncio.open_connection", AsyncMock(side_effect=error)):
        assert await _async_read_certificate(MOCK_HOST, MOCK_PORT) is None


async def _start_user_flow(hass: HomeAssistant) -> ConfigFlowResult:
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def _start_zeroconf_confirm_flow(hass: HomeAssistant) -> ConfigFlowResult:
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_make_zeroconf_info()
    )


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "start_flow",
    [
        pytest.param(_start_user_flow, id="user"),
        pytest.param(_start_zeroconf_confirm_flow, id="zeroconf_confirm"),
    ],
)
async def test_cannot_connect_then_recovers(
    hass: HomeAssistant,
    start_flow: Callable[[HomeAssistant], Awaitable[ConfigFlowResult]],
) -> None:
    """After a connection error, resubmitting valid info still succeeds."""
    result = await start_flow(hass)

    with patch(
        "aiohttp.ClientSession.ws_connect",
        side_effect=aiohttp.ClientConnectionError("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(PATCH_TRY_CONNECT, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == MOCK_HOST


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Duplicate gateway is rejected with already_configured abort."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HOSTNAME,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_FINGERPRINT: MOCK_FINGERPRINT,
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(PATCH_TRY_CONNECT, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_discovery_and_confirm(hass: HomeAssistant) -> None:
    """Zeroconf discovery shows a confirmation form, then creates the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_make_zeroconf_info(),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    with patch(PATCH_TRY_CONNECT, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "GARDENA-123456"
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["data"][CONF_PORT] == MOCK_PORT


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_confirm_cert_unreachable(hass: HomeAssistant) -> None:
    """Confirming a discovered gateway needs a readable certificate to pin."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_make_zeroconf_info()
    )

    with patch(PATCH_READ_CERTIFICATE, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    await _finish_flow(hass, result["flow_id"])


def _zeroconf_entry(host: str, port: int) -> MockConfigEntry:
    """Return a configured gateway that is pinned to the mock certificate."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HOSTNAME,
        data={
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_FINGERPRINT: MOCK_FINGERPRINT,
        },
    )


async def test_zeroconf_already_configured(hass: HomeAssistant) -> None:
    """Zeroconf rediscovery refreshes host and port of the pinned gateway.

    The gateway keeps its host but advertises a new port, so the unique-id
    match must run (and persist the update) before the host match aborts.
    """
    entry = _zeroconf_entry(MOCK_HOST, 1234)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_make_zeroconf_info(),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == MOCK_HOST
    assert entry.data[CONF_PORT] == MOCK_PORT


@pytest.mark.parametrize(
    "certificate",
    [
        _GatewayCertificate("cd" * 32, MOCK_HOSTNAME),
        None,
    ],
    ids=["other_certificate", "unreachable"],
)
async def test_zeroconf_ignores_unverified_address(
    hass: HomeAssistant,
    mock_read_certificate: MagicMock,
    certificate: _GatewayCertificate | None,
) -> None:
    """An announcement that cannot prove the pinned certificate changes nothing."""
    mock_read_certificate.return_value = certificate
    entry = _zeroconf_entry("192.168.1.50", 1234)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_make_zeroconf_info(),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.1.50"
    assert entry.data[CONF_PORT] == 1234


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_confirm_cannot_connect(hass: HomeAssistant) -> None:
    """Failed connection at zeroconf confirmation shows an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_make_zeroconf_info(),
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "aiohttp.ClientSession.ws_connect",
        side_effect=aiohttp.ClientConnectionError("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    await _finish_flow(hass, result["flow_id"])


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_success(hass: HomeAssistant) -> None:
    """Successful reconfiguration updates entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HOSTNAME,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_FINGERPRINT: MOCK_FINGERPRINT,
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_host = "192.168.1.200"
    with patch(PATCH_TRY_CONNECT, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: new_host, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == new_host
    assert entry.unique_id == MOCK_HOSTNAME


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_pins_new_certificate(hass: HomeAssistant) -> None:
    """Reconfiguring accepts a regenerated gateway certificate."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HOSTNAME,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_FINGERPRINT: MOCK_FINGERPRINT,
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    with (
        patch(PATCH_TRY_CONNECT, return_value=None) as try_connect,
        patch(
            PATCH_READ_CERTIFICATE,
            return_value=_GatewayCertificate(OTHER_FINGERPRINT, MOCK_HOSTNAME),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_FINGERPRINT] == OTHER_FINGERPRINT
    assert try_connect.call_args.args[-1] == OTHER_FINGERPRINT


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_cert_unreachable(hass: HomeAssistant) -> None:
    """Reconfiguring needs a readable certificate to pin."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HOSTNAME,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_FINGERPRINT: MOCK_FINGERPRINT,
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    with patch(PATCH_READ_CERTIFICATE, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    await _finish_reconfigure_flow(hass, result["flow_id"])
    assert entry.data[CONF_FINGERPRINT] == MOCK_FINGERPRINT


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_cannot_connect(hass: HomeAssistant) -> None:
    """Failed connection during reconfigure keeps the form open."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HOSTNAME,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_FINGERPRINT: MOCK_FINGERPRINT,
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "aiohttp.ClientSession.ws_connect",
        side_effect=aiohttp.ClientConnectionError("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.200",
                CONF_PORT: MOCK_PORT,
                CONF_PASSWORD: MOCK_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    await _finish_reconfigure_flow(hass, result["flow_id"])


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Return a mock coordinator standing in for the real gateway connection."""
    coordinator = MagicMock()
    coordinator.includable_devices = {}
    coordinator.async_include_device = AsyncMock(return_value=None)
    return coordinator


async def test_inclusion_subentry_no_devices(
    hass: HomeAssistant, mock_coordinator: MagicMock
) -> None:
    """Subentry flow aborts when no includable devices are advertising."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HOSTNAME,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_FINGERPRINT: MOCK_FINGERPRINT,
        },
    )
    entry.add_to_hass(hass)
    entry.runtime_data = mock_coordinator

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": "user"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_inclusion_subentry_success(
    hass: HomeAssistant, mock_coordinator: MagicMock
) -> None:
    """Subentry flow creates a subentry when inclusion succeeds."""
    instance_id = "instance-abc"
    device_id = "device-xyz"
    mock_coordinator.includable_devices = {
        instance_id: IncludableDeviceInfo(
            instance_id=instance_id,
            service="some-service",
            device_id=device_id,
            device_name="GARDENA Device 001",
            supported=True,
        )
    }
    mock_coordinator.async_include_device = AsyncMock(return_value=device_id)
    mock_coordinator.data = {}

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HOSTNAME,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_FINGERPRINT: MOCK_FINGERPRINT,
        },
    )
    entry.add_to_hass(hass)
    entry.runtime_data = mock_coordinator

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": "user"},
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"device": instance_id}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["device_id"] == device_id


async def test_inclusion_subentry_reuses_retained_subentry(
    hass: HomeAssistant, mock_coordinator: MagicMock
) -> None:
    """Including a device again keeps its existing subentry."""
    instance_id = "instance-abc"
    device_id = "device-xyz"
    mock_coordinator.includable_devices = {
        instance_id: IncludableDeviceInfo(
            instance_id=instance_id,
            service="some-service",
            device_id=device_id,
            device_name="GARDENA Device 001",
            supported=True,
        )
    }
    mock_coordinator.async_include_device = AsyncMock(return_value=device_id)
    mock_coordinator.data = {device_id: MagicMock()}

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HOSTNAME,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_FINGERPRINT: MOCK_FINGERPRINT,
        },
        subentries_data=[
            ConfigSubentryData(
                data={"device_id": device_id},
                subentry_type="device",
                title="GARDENA Device 001",
                unique_id=device_id,
            )
        ],
    )
    entry.add_to_hass(hass)
    entry.runtime_data = mock_coordinator

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": "user"},
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"device": instance_id}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_restored"
    assert len(entry.subentries) == 1
    mock_coordinator.async_set_updated_data.assert_called_once_with(
        mock_coordinator.data
    )


async def test_inclusion_subentry_failed(
    hass: HomeAssistant, mock_coordinator: MagicMock
) -> None:
    """Subentry flow shows an error when the gateway rejects inclusion."""
    instance_id = "instance-abc"
    mock_coordinator.includable_devices = {
        instance_id: IncludableDeviceInfo(
            instance_id=instance_id,
            service="some-service",
            device_id="device-xyz",
            device_name="GARDENA Device 001",
            supported=True,
        )
    }
    mock_coordinator.async_include_device = AsyncMock(return_value=None)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HOSTNAME,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_FINGERPRINT: MOCK_FINGERPRINT,
        },
    )
    entry.add_to_hass(hass)
    entry.runtime_data = mock_coordinator

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": "user"},
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"device": instance_id}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "inclusion_failed"}

    mock_coordinator.async_include_device = AsyncMock(return_value="device-xyz")
    mock_coordinator.data = {}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"device": instance_id}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_outdated_firmware(hass: HomeAssistant) -> None:
    """A certificate without the gateway name asks the user to let it update."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        PATCH_READ_CERTIFICATE,
        return_value=_GatewayCertificate(MOCK_FINGERPRINT, None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "outdated_firmware"}

    await _finish_flow(hass, result["flow_id"])


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_confirm_outdated_firmware(hass: HomeAssistant) -> None:
    """The discovery form also asks the user to let an outdated gateway update."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_make_zeroconf_info()
    )

    with patch(
        PATCH_READ_CERTIFICATE,
        return_value=_GatewayCertificate(MOCK_FINGERPRINT, None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "outdated_firmware"}

    await _finish_flow(hass, result["flow_id"])


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_outdated_firmware(hass: HomeAssistant) -> None:
    """Reconfiguring needs a gateway whose certificate carries its name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HOSTNAME,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_FINGERPRINT: MOCK_FINGERPRINT,
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    with patch(
        PATCH_READ_CERTIFICATE,
        return_value=_GatewayCertificate(MOCK_FINGERPRINT, None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "outdated_firmware"}

    await _finish_reconfigure_flow(hass, result["flow_id"])


async def test_reconfigure_rejects_other_gateway(hass: HomeAssistant) -> None:
    """The new address must belong to the gateway the entry was set up for."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HOSTNAME,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_FINGERPRINT: MOCK_FINGERPRINT,
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    with patch(
        PATCH_READ_CERTIFICATE,
        return_value=_GatewayCertificate(OTHER_FINGERPRINT, "GARDENA-999999"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.200", CONF_PORT: MOCK_PORT, CONF_PASSWORD: ""},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert entry.data[CONF_HOST] == MOCK_HOST
    assert entry.data[CONF_FINGERPRINT] == MOCK_FINGERPRINT


def _reauth_entry() -> MockConfigEntry:
    """Return an entry whose stored password the gateway rejects."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HOSTNAME,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_FINGERPRINT: MOCK_FINGERPRINT,
        },
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_success(hass: HomeAssistant) -> None:
    """Reauthentication stores the new password and keeps the rest."""
    entry = _reauth_entry()
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(PATCH_TRY_CONNECT, return_value=None) as try_connect:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new-password"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-password"
    assert entry.data[CONF_HOST] == MOCK_HOST
    assert entry.data[CONF_FINGERPRINT] == MOCK_FINGERPRINT
    assert try_connect.call_args.args[1:] == (
        MOCK_HOST,
        MOCK_PORT,
        "new-password",
        MOCK_FINGERPRINT,
    )


@pytest.mark.parametrize("error", ["invalid_auth", "cannot_connect", "unknown"])
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_errors_can_be_recovered(hass: HomeAssistant, error: str) -> None:
    """A failed attempt shows the error and the flow still finishes."""
    entry = _reauth_entry()
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)

    with patch(PATCH_TRY_CONNECT, return_value=error):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "wrong"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert entry.data[CONF_PASSWORD] == MOCK_PASSWORD

    with patch(PATCH_TRY_CONNECT, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "right"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "right"
