"""Tests for the Daikin config flow."""

import asyncio
from collections.abc import Generator
from ipaddress import ip_address
import threading
import time
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from aiohttp import ClientError, web_exceptions
from pydaikin.exceptions import DaikinException
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin.const import DOMAIN, KEY_MAC
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

MAC = "AABBCCDDEEFF"
HOST = "127.0.0.1"


def _zeroconf_info(host: str) -> ZeroconfServiceInfo:
    """Return zeroconf discovery info for a host."""
    return ZeroconfServiceInfo(
        ip_address=ip_address(host),
        ip_addresses=[ip_address(host)],
        hostname="mock_hostname",
        name="mock_name",
        port=None,
        properties={},
        type="mock_type",
    )


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.daikin.async_setup_entry", return_value=None
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_daikin():
    """Mock pydaikin."""

    async def mock_daikin_factory(*args, **kwargs):
        """Mock the init function in pydaikin."""
        return Appliance

    with patch(
        "homeassistant.components.daikin.config_flow.DaikinFactory"
    ) as Appliance:
        type(Appliance).mac = PropertyMock(return_value="AABBCCDDEEFF")
        Appliance.side_effect = mock_daikin_factory
        yield Appliance


@pytest.fixture
def mock_daikin_discovery():
    """Mock pydaikin Discovery."""
    with patch("homeassistant.components.daikin.config_flow.Discovery") as Discovery:
        Discovery().poll.return_value = {
            "127.0.01": {"mac": "AABBCCDDEEFF", "id": "test"}
        }.values()
        yield Discovery


async def test_user(hass: HomeAssistant, mock_daikin) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: HOST},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][KEY_MAC] == MAC
    assert result["result"].unique_id == MAC


async def test_abort_if_already_setup(hass: HomeAssistant, mock_daikin) -> None:
    """Test we abort if Daikin is already setup."""
    MockConfigEntry(domain="daikin", unique_id=MAC).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: HOST},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("s_effect", "reason"),
    [
        (TimeoutError, "cannot_connect"),
        (ClientError, "cannot_connect"),
        (web_exceptions.HTTPForbidden, "invalid_auth"),
        (DaikinException("Empty values."), "cannot_connect"),
        (DaikinException, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_device_abort(
    hass: HomeAssistant,
    mock_daikin: MagicMock,
    s_effect: type[Exception] | Exception,
    reason: str,
) -> None:
    """Test device abort."""
    mock_daikin.side_effect = s_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: HOST},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}
    assert result["step_id"] == "user"

    mock_daikin.side_effect = AsyncMock(return_value=mock_daikin)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: HOST},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_daikin")
async def test_api_password_abort(hass: HomeAssistant) -> None:
    """Test device abort."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: HOST, CONF_API_KEY: "aa", CONF_PASSWORD: "aa"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "api_password"}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: HOST},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("source", "data", "unique_id"),
    [
        (
            SOURCE_ZEROCONF,
            ZeroconfServiceInfo(
                ip_address=ip_address(HOST),
                ip_addresses=[ip_address(HOST)],
                hostname="mock_hostname",
                name="mock_name",
                port=None,
                properties={},
                type="mock_type",
            ),
            MAC,
        ),
    ],
)
async def test_discovery_zeroconf(
    hass: HomeAssistant, mock_daikin, mock_daikin_discovery, source, data, unique_id
) -> None:
    """Test discovery/zeroconf step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source},
        data=data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    MockConfigEntry(domain="daikin", unique_id=unique_id).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "unique_id": unique_id}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: HOST},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source},
        data=data,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.usefixtures("mock_daikin")
async def test_discovery_zeroconf_runs_in_executor(hass: HomeAssistant) -> None:
    """Test the blocking UDP discovery runs off the event loop thread."""
    threads: list[int] = []

    def mock_discovery() -> MagicMock:
        threads.append(threading.get_ident())
        discovery = MagicMock()

        def mock_poll(ip: str) -> list[dict[str, str]]:
            threads.append(threading.get_ident())
            return [{"mac": MAC, "id": "test"}]

        discovery.poll.side_effect = mock_poll
        return discovery

    with patch(
        "homeassistant.components.daikin.config_flow.Discovery",
        side_effect=mock_discovery,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info(HOST)
        )

    assert result["type"] is FlowResultType.FORM
    assert len(threads) == 2
    assert threading.get_ident() not in threads


@pytest.mark.usefixtures("mock_daikin")
async def test_discovery_zeroconf_polls_serialized(hass: HomeAssistant) -> None:
    """Test concurrent zeroconf flows do not poll at the same time."""
    lock = threading.Lock()
    active = 0
    max_active = 0

    def mock_poll(ip: str) -> list[dict[str, str]]:
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        # Keep the poll busy long enough for an unserialized one to overlap
        time.sleep(0.1)
        with lock:
            active -= 1
        return [{"mac": ip, "id": "test"}]

    with patch("homeassistant.components.daikin.config_flow.Discovery") as discovery:
        discovery.return_value.poll.side_effect = mock_poll
        results = await asyncio.gather(
            *(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_ZEROCONF},
                    data=_zeroconf_info(host),
                )
                for host in ("127.0.0.1", "127.0.0.2")
            )
        )

    assert [result["type"] for result in results] == [FlowResultType.FORM] * 2
    assert discovery.return_value.poll.call_count == 2
    assert max_active == 1
