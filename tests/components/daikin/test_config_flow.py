"""Tests for the Daikin config flow."""

from ipaddress import ip_address
from unittest.mock import PropertyMock, patch

from aiohttp import ClientError, web_exceptions
from pydaikin.exceptions import DaikinException
import pytest

from homeassistant.components import zeroconf
from homeassistant.components.daikin.const import KEY_MAC
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MAC = "AABBCCDDEEFF"
HOST = "127.0.0.1"


@pytest.fixture
def mock_daikin():
    """Mock pydaikin."""

    async def mock_daikin_factory(*args, **kwargs):
        """Mock the init function in pydaikin."""
        return Appliance

    with patch("homeassistant.components.daikin.config_flow.Appliance") as Appliance:
        type(Appliance).mac = PropertyMock(return_value="AABBCCDDEEFF")
        Appliance.factory.side_effect = mock_daikin_factory
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
        "daikin",
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        "daikin",
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][KEY_MAC] == MAC


async def test_abort_if_already_setup(hass: HomeAssistant, mock_daikin) -> None:
    """Test we abort if Daikin is already setup."""
    MockConfigEntry(domain="daikin", unique_id=MAC).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "daikin",
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, KEY_MAC: MAC},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("s_effect", "reason"),
    [
        (TimeoutError, "cannot_connect"),
        (ClientError, "cannot_connect"),
        (web_exceptions.HTTPForbidden, "invalid_auth"),
        (DaikinException, "unknown"),
        (Exception, "unknown"),
    ],
)
async def test_device_abort(hass: HomeAssistant, mock_daikin, s_effect, reason) -> None:
    """Test device abort."""
    mock_daikin.factory.side_effect = s_effect

    result = await hass.config_entries.flow.async_init(
        "daikin",
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, KEY_MAC: MAC},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}
    assert result["step_id"] == "user"


async def test_api_password_abort(hass: HomeAssistant) -> None:
    """Test device abort."""
    result = await hass.config_entries.flow.async_init(
        "daikin",
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_API_KEY: "aa", CONF_PASSWORD: "aa"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "api_password"}
    assert result["step_id"] == "user"


@pytest.mark.parametrize(
    ("source", "data", "unique_id"),
    [
        (
            SOURCE_ZEROCONF,
            zeroconf.ZeroconfServiceInfo(
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
        "daikin",
        context={"source": source},
        data=data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    MockConfigEntry(domain="daikin", unique_id=unique_id).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "daikin",
        context={"source": SOURCE_USER, "unique_id": unique_id},
        data={CONF_HOST: HOST},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    result = await hass.config_entries.flow.async_init(
        "daikin",
        context={"source": source},
        data=data,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
