"""Tests for the Poolside config flow."""

from collections.abc import Generator
from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from aiopoolside import (
    PairingApproved,
    PairingBusy,
    PairingError,
    PairingInvalid,
    PairingPending,
    PairingRejected,
    PairingTimedOut,
    PoolsideAuthError,
    PoolsideConnectionError,
)
import pytest

from homeassistant.components.poolside.const import (
    CONF_CLIENT_PRIVATE_KEY,
    CONF_CONTROLLER_PUBLIC_KEY,
    CONF_CONTROLLER_UUID,
    CONF_EXPOSE_POOL_DEVICES,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import (
    TEST_CONTROLLER_UUID,
    TEST_HOST,
    TEST_PORT,
    TEST_SITE,
    TEST_SITE_NAME,
)

from tests.common import MockConfigEntry

ZEROCONF_INFO = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.50"),
    ip_addresses=[ip_address("192.168.1.50")],
    hostname="poolside-controller.local.",
    name=f"poolside-{TEST_CONTROLLER_UUID}._poolside._tcp.local.",
    type="_poolside._tcp.local.",
    port=TEST_PORT,
    properties={
        "uuid": TEST_CONTROLLER_UUID,
        "name": TEST_SITE_NAME,
        "version": "1.2.3",
        "api": "1",
    },
)

APPROVED = PairingApproved(
    fingerprint="AB12-CD34-EF56-7890",
    controller_public_key=b"\x02" * 32,
    controller_uuid=TEST_CONTROLLER_UUID,
)
PENDING = PairingPending(
    fingerprint="AB12-CD34-EF56-7890", expires_at="2026-01-01T00:00:00Z"
)


@pytest.fixture(autouse=True)
def mock_finish_client() -> Generator[MagicMock]:
    """Mock PoolsideClient for the connectivity test and the auto-triggered setup.

    Creating an entry triggers Home Assistant to set it up immediately, which
    goes through `homeassistant.components.poolside.PoolsideClient`, a
    separate binding from the one `config_flow.py` uses for its own
    test-before-configure check.
    """
    with (
        patch(
            "homeassistant.components.poolside.config_flow.PoolsideClient",
            autospec=True,
        ) as mock_class,
        patch(
            "homeassistant.components.poolside.PoolsideClient",
            new=mock_class,
        ),
    ):
        mock_class.return_value.async_connect = AsyncMock()
        mock_class.return_value.async_disconnect = AsyncMock()
        mock_class.return_value.async_get_control_layout = AsyncMock(
            return_value=(TEST_SITE, [])
        )
        yield mock_class


async def test_user_flow_immediate_approval(hass: HomeAssistant) -> None:
    """An already-paired client is approved immediately, with no progress step."""
    with patch(
        "homeassistant.components.poolside.config_flow.async_request_pairing",
        return_value=(MagicMock(), APPROVED),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_SITE_NAME
    assert result["data"][CONF_CONTROLLER_UUID] == TEST_CONTROLLER_UUID
    assert CONF_CLIENT_PRIVATE_KEY in result["data"]
    assert CONF_CONTROLLER_PUBLIC_KEY in result["data"]


async def test_user_flow_pending_then_approved(hass: HomeAssistant) -> None:
    """A fresh pairing shows a progress step, then finishes once approved."""
    with (
        patch(
            "homeassistant.components.poolside.config_flow.async_request_pairing",
            return_value=(MagicMock(), PENDING),
        ),
        patch(
            "homeassistant.components.poolside.config_flow.async_await_pairing_result",
            return_value=APPROVED,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "pair"
        placeholders = result["description_placeholders"]
        assert placeholders is not None
        assert placeholders["fingerprint"] == PENDING.fingerprint

        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(PairingRejected(), "pair_rejected", id="rejected"),
        pytest.param(PairingTimedOut(), "pair_timeout", id="timeout"),
        pytest.param(PairingBusy(), "pair_busy", id="busy"),
        pytest.param(PairingInvalid(), "pair_failed", id="invalid"),
        pytest.param(PairingError(), "pair_failed", id="generic-error"),
    ],
)
async def test_user_flow_pending_then_denied(
    hass: HomeAssistant, exception: Exception, reason: str
) -> None:
    """A pending pairing that ends unfavorably aborts with the matching reason."""
    with (
        patch(
            "homeassistant.components.poolside.config_flow.async_request_pairing",
            return_value=(MagicMock(), PENDING),
        ),
        patch(
            "homeassistant.components.poolside.config_flow.async_await_pairing_result",
            side_effect=exception,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
        )
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(PairingRejected(), "pair_rejected", id="rejected"),
        pytest.param(PairingTimedOut(), "pair_timeout", id="timeout"),
        pytest.param(PairingBusy(), "pair_busy", id="busy"),
        pytest.param(PairingInvalid(), "pair_failed", id="invalid"),
    ],
)
async def test_user_flow_immediate_denied(
    hass: HomeAssistant, exception: Exception, reason: str
) -> None:
    """An immediate rejection/timeout/busy response aborts with the matching reason."""
    with patch(
        "homeassistant.components.poolside.config_flow.async_request_pairing",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(aiohttp.ClientError(), id="client-error"),
        pytest.param(PairingError(), id="pairing-error"),
    ],
)
async def test_user_flow_request_error_then_recover(
    hass: HomeAssistant, exception: Exception
) -> None:
    """A failed pairing request shows an error and the flow can be retried."""
    with patch(
        "homeassistant.components.poolside.config_flow.async_request_pairing",
        side_effect=exception,
    ) as mock_request:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

        mock_request.side_effect = None
        mock_request.return_value = (MagicMock(), APPROVED)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CONTROLLER_UUID] == TEST_CONTROLLER_UUID


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(PoolsideAuthError(), id="auth-error"),
        pytest.param(PoolsideConnectionError(), id="connection-error"),
    ],
)
async def test_finish_connect_error_then_recover(
    hass: HomeAssistant, mock_finish_client: MagicMock, exception: Exception
) -> None:
    """A failed session handshake shows an error and the flow can be retried."""
    mock_finish_client.return_value.async_connect.side_effect = exception

    with patch(
        "homeassistant.components.poolside.config_flow.async_request_pairing",
        return_value=(MagicMock(), APPROVED),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

        mock_finish_client.return_value.async_connect.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_SITE_NAME


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Pairing with an already-configured controller aborts."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.poolside.config_flow.async_request_pairing",
        return_value=(MagicMock(), APPROVED),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A reauth flow reuses the stored keypair and reloads the entry on success."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.poolside.config_flow.async_request_pairing",
        return_value=(MagicMock(), APPROVED),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_CONTROLLER_UUID] == TEST_CONTROLLER_UUID


async def test_zeroconf_discovery_confirm_flow(hass: HomeAssistant) -> None:
    """Discovering a controller via mDNS shows a confirm step, then pairs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=ZEROCONF_INFO
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    with patch(
        "homeassistant.components.poolside.config_flow.async_request_pairing",
        return_value=(MagicMock(), APPROVED),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == ZEROCONF_INFO.host
    assert result["data"][CONF_CONTROLLER_UUID] == TEST_CONTROLLER_UUID


async def test_zeroconf_discovery_missing_uuid_aborts(hass: HomeAssistant) -> None:
    """A discovery record without a uuid TXT property aborts immediately."""
    info = ZeroconfServiceInfo(
        ip_address=ZEROCONF_INFO.ip_address,
        ip_addresses=ZEROCONF_INFO.ip_addresses,
        hostname=ZEROCONF_INFO.hostname,
        name=ZEROCONF_INFO.name,
        type=ZEROCONF_INFO.type,
        port=ZEROCONF_INFO.port,
        properties={},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_discovery_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Rediscovering an already-configured controller aborts and updates host/port."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=ZEROCONF_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("setup_integration")
async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The options flow updates the pool device exposure setting."""
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_EXPOSE_POOL_DEVICES: False}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_EXPOSE_POOL_DEVICES] is False
