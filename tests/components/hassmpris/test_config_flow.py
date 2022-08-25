"""Test the MPRIS media playback remote control config flow."""
from unittest.mock import patch

import contextlib

import hassmpris_client
import pskca

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.hassmpris.const import (
    CONF_CAKES_PORT,
    DOMAIN,
    STEP_CONFIRM,
    STEP_ZEROCONF_CONFIRM,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


class MockECDH:
    """Mock ECDH."""

    derived_key = b"012345678901234567890123456789"


class MockCakesClient:
    """Mock CAKES client."""

    def __init__(self, exc=None):
        self.exc = exc

    def __call__(self, *unused_args, **unused_kw):
        return self

    async def obtain_verifier(self):
        """Fake verifier."""
        if self.exc:
            raise self.exc()
        return MockECDH()

    async def obtain_certificate(self):
        """Fake certificate."""
        # Any silly certificate will do, so we make one.
        if self.exc:
            raise self.exc()
        cert = pskca.create_certificate_and_key()[0]
        return cert, [cert]


class MockMprisClient:
    """Mock MPRIS client."""

    def __init__(self, *unused_a, **unused_kw):
        pass

    async def ping(self):
        """Fake successful ping."""


_hostinfo = {
    "host": "1.1.1.1",
    "cakes_port": 40052,
    "mpris_port": 40051,
}

_zeroconfinfo = zeroconf.ZeroconfServiceInfo(
    host="127.0.0.1",
    addresses=[],
    port=40051,
    hostname="uniqueid",
    name="thename",
    properties={CONF_CAKES_PORT: "40052"},
    type="_hassmpris._tcp.local.",
)


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test we get the user form and, upon success, go to confirm step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    with patch("hassmpris_client.AsyncCAKESClient", return_value=MockCakesClient()):
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


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test we get the user form and then fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "hassmpris_client.AsyncCAKESClient",
        MockCakesClient(exc=hassmpris_client.ClientException),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _hostinfo,
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.ABORT
        assert result2["reason"] == "cannot_connect"


async def test_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test we get the user form and, upon success, go to confirm step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconfinfo,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == STEP_ZEROCONF_CONFIRM

    with patch("hassmpris_client.AsyncCAKESClient", return_value=MockCakesClient()):
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


# Possible additional tests:
#
# * test what happens when the user rejects the match
# * test what happens when the other side rejects the match
# * test what happens when cannot connect to CAKES
