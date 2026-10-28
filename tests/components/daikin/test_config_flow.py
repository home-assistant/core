"""Tests for the Daikin config flow."""

from collections.abc import Generator
from ipaddress import ip_address
from unittest.mock import ANY, AsyncMock, MagicMock, PropertyMock, patch

from aiohttp import ClientError, web_exceptions
from pydaikin.exceptions import DaikinException
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin.const import DOMAIN, KEY_MAC
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PASSWORD, CONF_UUID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

MAC = "AABBCCDDEEFF"
HOST = "127.0.0.1"


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


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Daikin config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=HOST,
        unique_id=MAC,
        data={
            CONF_HOST: HOST,
            KEY_MAC: MAC,
            CONF_API_KEY: None,
            CONF_UUID: None,
            CONF_PASSWORD: None,
        },
    )


@pytest.mark.usefixtures("mock_daikin")
async def test_reconfigure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring the Daikin device."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.2", CONF_API_KEY: "secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_HOST: "127.0.0.2",
        KEY_MAC: MAC,
        CONF_API_KEY: "secret",
        CONF_UUID: ANY,
        CONF_PASSWORD: None,
    }


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        pytest.param(TimeoutError, "cannot_connect", id="timeout"),
        pytest.param(ClientError, "cannot_connect", id="client_error"),
        pytest.param(web_exceptions.HTTPForbidden, "invalid_auth", id="invalid_auth"),
        pytest.param(DaikinException, "cannot_connect", id="daikin_exception"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_daikin: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test reconfigure errors are shown and the flow can recover."""
    mock_config_entry.add_to_hass(hass)
    original_side_effect = mock_daikin.side_effect
    mock_daikin.side_effect = side_effect

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.2"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": reason}

    mock_daikin.side_effect = original_side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.2"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "127.0.0.2"


@pytest.mark.usefixtures("mock_daikin")
async def test_reconfigure_api_password(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring with both an API key and a password shows an error."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.2", CONF_API_KEY: "aa", CONF_PASSWORD: "aa"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "api_password"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.2", CONF_PASSWORD: "aa"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "aa"


@pytest.mark.usefixtures("mock_daikin")
async def test_reconfigure_unique_id_mismatch(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring to a different device aborts."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id="other")

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.2"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data[CONF_HOST] == HOST


@pytest.mark.usefixtures("mock_daikin")
async def test_reconfigure_host_based_unique_id(hass: HomeAssistant) -> None:
    """Test reconfiguring an entry with a host based unique ID keeps it."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=HOST, data={CONF_HOST: HOST, KEY_MAC: HOST}
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.2"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "127.0.0.2"
    # Left for the migration on setup, which renames the entities
    assert entry.unique_id == HOST
    assert entry.data[KEY_MAC] == HOST


@pytest.mark.usefixtures("mock_daikin")
async def test_reconfigure_host_based_unique_id_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test reconfiguring a host based entry to the host of another entry aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=HOST, data={CONF_HOST: HOST, KEY_MAC: HOST}
    )
    entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN, unique_id=MAC, data={CONF_HOST: "127.0.0.2", KEY_MAC: MAC}
    ).add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.2"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == HOST
