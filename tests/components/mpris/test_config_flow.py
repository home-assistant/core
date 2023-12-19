"""Test the MPRIS media playback remote control config flow."""
from ipaddress import IPv4Address
from typing import Any
from unittest.mock import patch

from hassmpris.proto import mpris_pb2
import hassmpris_client
import pskca
import pytest

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.mpris.config_flow import _genuid
from homeassistant.components.mpris.const import (
    CONF_CAKES_PORT,
    CONF_HOST,
    CONF_MPRIS_PORT,
    DOMAIN,
    REASON_CANNOT_CONNECT,
    REASON_CANNOT_DECRYPT,
    REASON_IGNORED,
    REASON_INVALID_ZEROCONF,
    REASON_REJECTED,
    REASON_TIMEOUT,
    STEP_CONFIRM,
    STEP_REAUTH_CONFIRM,
    STEP_ZEROCONF_CONFIRM,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CACHED_KEY: Any = None


class MockECDH:
    """Mock ECDH."""

    derived_key = b"012345678901234567890123456789"


class MockCakesClient:
    """Mock CAKES client."""

    def __init__(self, exc=None, exc_cert=None):
        """Initialize the mock."""
        self.exc = exc
        self.exc_cert = exc_cert

    def __call__(self, *unused_args, **unused_kw):
        """Return self to keep it going across the call chain."""
        return self

    async def obtain_verifier(self):
        """Fake verifier."""
        if self.exc:
            raise self.exc()
        return MockECDH()

    async def obtain_certificate(self):
        """Fake certificate."""
        global CACHED_KEY
        # Any silly certificate will do, so we make one.
        if self.exc_cert:
            raise self.exc_cert()
        if CACHED_KEY is None:
            CACHED_KEY = pskca.create_certificate_and_key()[0]
        cert = CACHED_KEY
        return cert, [cert]


class MockMprisClient:
    """Mock MPRIS client."""

    def __init__(self, *unused_a, **unused_kw):
        """Initialize the mock."""
        self.host = "localhost"

    async def ping(self):
        """Fake successful ping."""

    async def close(self):
        """Fake close."""

    async def stream_updates(self, timeout=5):
        """Fake stream updates."""
        yield mpris_pb2.MPRISUpdateReply(
            player=mpris_pb2.MPRISPlayerUpdate(
                player_id="VLC",
                status=mpris_pb2.PlayerStatus.GONE,
                json_metadata="",
                properties=mpris_pb2.MPRISPlayerProperties(**{}),
            )
        )
        pytest.fail()


class MockCoordinator:
    """Mock the MPRIS coordinator."""

    pass


class fakecsrkey:
    """Creates CSR and key request, caching the same one between calls."""

    def __init__(self):
        """Initialize the faker."""
        self.csr, self.key = pskca.create_certificate_signing_request()

    def __call__(self):
        """Return the CSR and key when the patch() patches pskca with this."""
        return self.csr, self.key


_hostinfo = {
    "host": "1.1.1.1",
    "cakes_port": 40052,
    "mpris_port": 40051,
}

_localhostinfo = {
    "host": "127.0.0.1",
    "cakes_port": 40052,
    "mpris_port": 40051,
}

_zeroconfinfo = zeroconf.ZeroconfServiceInfo(
    ip_address=IPv4Address("127.0.0.1"),
    ip_addresses=[IPv4Address("127.0.0.1")],
    port=40051,
    hostname="uniqueid",
    name="thename",
    properties={CONF_CAKES_PORT: "40052"},
    type="_hassmpris._tcp.local.",
)

_zeroconf_entry_data = {
    CONF_HOST: _zeroconfinfo.host,
    CONF_CAKES_PORT: int(_zeroconfinfo.properties[CONF_CAKES_PORT]),
    CONF_MPRIS_PORT: _zeroconfinfo.port,
}


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test we get the user form and, upon success, go to confirm step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "hassmpris_client.AsyncCAKESClient", return_value=MockCakesClient()
    ), patch("pskca.create_certificate_signing_request", fakecsrkey()):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _hostinfo,
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == STEP_CONFIRM

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "emojis": "doesn't matter",
            },
        )
        await hass.async_block_till_done()

        assert result3["type"] == FlowResultType.CREATE_ENTRY

    # Now we test that the entry is not actually added twice.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _hostinfo,
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT


async def test_user_flow_errors(hass: HomeAssistant) -> None:
    """Test we get the user form and then fails."""
    with patch("pskca.create_certificate_signing_request", fakecsrkey()):
        for exc, reason in [
            (hassmpris_client.ClientException, REASON_CANNOT_CONNECT),
            (hassmpris_client.Timeout, REASON_TIMEOUT),
        ]:
            # test the connection error.
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            with patch(
                "hassmpris_client.AsyncCAKESClient",
                MockCakesClient(exc=exc),
            ):
                result = await hass.config_entries.flow.async_configure(
                    result["flow_id"],
                    _hostinfo,
                )
                await hass.async_block_till_done()

                assert result["type"] == FlowResultType.ABORT
                assert result["reason"] == reason

        for exc, reason in [
            (hassmpris_client.CannotConnect, REASON_CANNOT_CONNECT),
            (hassmpris_client.Timeout, REASON_TIMEOUT),
            (hassmpris_client.ClientException, REASON_CANNOT_CONNECT),
            (hassmpris_client.CannotDecrypt, REASON_CANNOT_DECRYPT),
            (hassmpris_client.Ignored, REASON_IGNORED),
            (hassmpris_client.Rejected, REASON_REJECTED),
        ]:
            # test the connection error.
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            with patch(
                "hassmpris_client.AsyncCAKESClient",
                MockCakesClient(exc_cert=exc),
            ):
                result = await hass.config_entries.flow.async_configure(
                    result["flow_id"],
                    _hostinfo,
                )
                await hass.async_block_till_done()

                assert result["type"] == FlowResultType.FORM
                assert result["step_id"] == STEP_CONFIRM

                result = await hass.config_entries.flow.async_configure(
                    result["flow_id"],
                    {
                        "emojis": "doesn't matter",
                    },
                )
                await hass.async_block_till_done()

                assert result["type"] == FlowResultType.ABORT
                assert result["reason"] == reason


async def test_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test we get the user form and, upon success, go to confirm step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconfinfo,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == STEP_ZEROCONF_CONFIRM

    with patch(
        "hassmpris_client.AsyncCAKESClient", return_value=MockCakesClient()
    ), patch(
        "hassmpris_client.AsyncMPRISClient", return_value=MockMprisClient()
    ), patch(
        "pskca.create_certificate_signing_request", fakecsrkey()
    ), patch(
        "homeassistant.components.mpris.media_player.MPRISCoordinator",
        MockCoordinator(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _localhostinfo,
        )
        await hass.async_block_till_done()
        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == STEP_CONFIRM

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "emojis": "doesn't matter",
            },
        )
        await hass.async_block_till_done()

        assert result3["type"] == FlowResultType.CREATE_ENTRY

        # Now we test that the entry is not actually added twice.
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=_zeroconfinfo,
        )
        assert result["type"] == FlowResultType.ABORT


async def test_invalid_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test we get the user form and, upon success, go to confirm step."""
    badinfo = zeroconf.ZeroconfServiceInfo(
        ip_address=IPv4Address("127.0.0.1"),
        ip_addresses=[IPv4Address("127.0.0.1")],
        port=40051,
        hostname="uniqueid",
        name="thename",
        properties={},  # No CAKES port!
        type="_hassmpris._tcp.local.",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=badinfo,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == REASON_INVALID_ZEROCONF


async def _generic_test_reauth_flow(
    hass: HomeAssistant,
    entry_data: dict[str, Any],
    mock_entry=MockConfigEntry,
) -> None:
    """Test reauth works correctly in the zeroconf case."""
    mock_entry.add_to_hass(hass)

    with patch(
        "hassmpris_client.AsyncCAKESClient", return_value=MockCakesClient()
    ), patch("pskca.create_certificate_signing_request", fakecsrkey()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "unique_id": mock_entry.unique_id,
                "entry_id": mock_entry.entry_id,
            },
            data=entry_data,
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == STEP_REAUTH_CONFIRM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: entry_data[CONF_HOST],
                CONF_CAKES_PORT: entry_data[CONF_CAKES_PORT],
                CONF_MPRIS_PORT: entry_data[CONF_MPRIS_PORT],
            },
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == STEP_CONFIRM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "emojis": "doesn't matter",
            },
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"


async def test_user_reauth_flow(hass: HomeAssistant) -> None:
    """Test reauth works correctly in the manually-configured case."""
    entry_data = {
        CONF_HOST: "127.0.0.1",
        CONF_CAKES_PORT: 1234,
        CONF_MPRIS_PORT: 4567,
    }
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=entry_data,
        unique_id="127.0.0.1:1234:4567",
    )
    await _generic_test_reauth_flow(hass, entry_data, mock_entry)


async def test_zeroconf_reauth_flow(hass: HomeAssistant) -> None:
    """Test reauth works correctly in the zeroconf case."""
    entry_data = _zeroconf_entry_data
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=entry_data,
        unique_id=_genuid(
            entry_data[CONF_HOST],
            entry_data[CONF_CAKES_PORT],
            entry_data[CONF_MPRIS_PORT],
        ),
    )
    await _generic_test_reauth_flow(hass, entry_data, mock_entry)


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test the options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_zeroconf_entry_data,
        unique_id="127.0.0.1:1234:5678",
        options={},
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.mpris.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
