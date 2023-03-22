"""Test the Plugwise config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

from plugwise.exceptions import (
    ConnectionFailedError,
    InvalidAuthentication,
    InvalidSetupError,
    InvalidXMLError,
    ResponseError,
    UnsupportedDeviceError,
)
import pytest

from homeassistant.components.plugwise.const import API, DEFAULT_PORT, DOMAIN, PW_TYPE
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SOURCE,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_HOST = "1.1.1.1"
TEST_HOSTNAME = "smileabcdef"
TEST_HOSTNAME2 = "stretchabc"
TEST_PASSWORD = "test_password"
TEST_PORT = 81
TEST_USERNAME = "smile"
TEST_USERNAME2 = "stretch"

TEST_DISCOVERY = ZeroconfServiceInfo(
    host=TEST_HOST,
    addresses=[TEST_HOST],
    # The added `-2` is to simulate mDNS collision
    hostname=f"{TEST_HOSTNAME}-2.local.",
    name="mock_name",
    port=DEFAULT_PORT,
    properties={
        "product": "smile",
        "version": "1.2.3",
        "hostname": f"{TEST_HOSTNAME}.local.",
    },
    type="mock_type",
)

TEST_DISCOVERY2 = ZeroconfServiceInfo(
    host=TEST_HOST,
    addresses=[TEST_HOST],
    hostname=f"{TEST_HOSTNAME2}.local.",
    name="mock_name",
    port=DEFAULT_PORT,
    properties={
        "product": "stretch",
        "version": "1.2.3",
        "hostname": f"{TEST_HOSTNAME2}.local.",
    },
    type="mock_type",
)

TEST_DISCOVERY_ANNA = ZeroconfServiceInfo(
    host=TEST_HOST,
    addresses=[TEST_HOST],
    hostname=f"{TEST_HOSTNAME}.local.",
    name="mock_name",
    port=DEFAULT_PORT,
    properties={
        "product": "smile_thermo",
        "version": "1.2.3",
        "hostname": f"{TEST_HOSTNAME}.local.",
    },
    type="mock_type",
)

TEST_DISCOVERY_ADAM = ZeroconfServiceInfo(
    host=TEST_HOST,
    addresses=[TEST_HOST],
    hostname=f"{TEST_HOSTNAME2}.local.",
    name="mock_name",
    port=DEFAULT_PORT,
    properties={
        "product": "smile_open_therm",
        "version": "1.2.3",
        "hostname": f"{TEST_HOSTNAME2}.local.",
    },
    type="mock_type",
)


@pytest.fixture(name="mock_smile")
def mock_smile():
    """Create a Mock Smile for testing exceptions."""
    with patch(
        "homeassistant.components.plugwise.config_flow.Smile",
    ) as smile_mock:
        smile_mock.ConnectionFailedError = ConnectionFailedError
        smile_mock.InvalidAuthentication = InvalidAuthentication
        smile_mock.InvalidSetupError = InvalidSetupError
        smile_mock.InvalidXMLError = InvalidXMLError
        smile_mock.ResponseError = ResponseError
        smile_mock.UnsupportedDeviceError = UnsupportedDeviceError
        smile_mock.return_value.connect.return_value = True
        yield smile_mock.return_value


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_smile_config_flow: MagicMock,
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {}
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: TEST_HOST,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "Test Smile Name"
    assert result2.get("data") == {
        CONF_HOST: TEST_HOST,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: DEFAULT_PORT,
        CONF_USERNAME: TEST_USERNAME,
        PW_TYPE: API,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_smile_config_flow.connect.mock_calls) == 1


@pytest.mark.parametrize(
    ("discovery", "username"),
    [
        (TEST_DISCOVERY, TEST_USERNAME),
        (TEST_DISCOVERY2, TEST_USERNAME2),
    ],
)
async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_smile_config_flow: MagicMock,
    discovery: ZeroconfServiceInfo,
    username: str,
) -> None:
    """Test config flow for smile devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=discovery,
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {}
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: TEST_PASSWORD},
    )
    await hass.async_block_till_done()

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "Test Smile Name"
    assert result2.get("data") == {
        CONF_HOST: TEST_HOST,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: DEFAULT_PORT,
        CONF_USERNAME: username,
        PW_TYPE: API,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_smile_config_flow.connect.mock_calls) == 1


async def test_zeroconf_flow_stretch(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_smile_config_flow: MagicMock,
) -> None:
    """Test config flow for stretch devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DISCOVERY2,
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {}
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: TEST_PASSWORD},
    )
    await hass.async_block_till_done()

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "Test Smile Name"
    assert result2.get("data") == {
        CONF_HOST: TEST_HOST,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: DEFAULT_PORT,
        CONF_USERNAME: TEST_USERNAME2,
        PW_TYPE: API,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_smile_config_flow.connect.mock_calls) == 1


async def test_zercoconf_discovery_update_configuration(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_smile_config_flow: MagicMock,
) -> None:
    """Test if a discovered device is configured and updated with new host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=CONF_NAME,
        data={
            CONF_HOST: "0.0.0.0",
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        unique_id=TEST_HOSTNAME,
    )
    entry.add_to_hass(hass)

    assert entry.data[CONF_HOST] == "0.0.0.0"

    # Test that an invalid discovery doesn't update the entry
    mock_smile_config_flow.connect.side_effect = ConnectionFailedError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DISCOVERY,
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    assert entry.data[CONF_HOST] == "0.0.0.0"

    mock_smile_config_flow.connect.side_effect = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DISCOVERY,
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    assert entry.data[CONF_HOST] == "1.1.1.1"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (ConnectionFailedError, "cannot_connect"),
        (InvalidAuthentication, "invalid_auth"),
        (InvalidSetupError, "invalid_setup"),
        (InvalidXMLError, "response_error"),
        (ResponseError, "response_error"),
        (RuntimeError, "unknown"),
        (UnsupportedDeviceError, "unsupported"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_smile_config_flow: MagicMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {}
    assert result.get("step_id") == "user"

    mock_smile_config_flow.connect.side_effect = side_effect
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: TEST_HOST, CONF_PASSWORD: TEST_PASSWORD},
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") == {"base": reason}
    assert result2.get("step_id") == "user"

    assert len(mock_setup_entry.mock_calls) == 0
    assert len(mock_smile_config_flow.connect.mock_calls) == 1

    mock_smile_config_flow.connect.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: TEST_HOST, CONF_PASSWORD: TEST_PASSWORD},
    )

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Test Smile Name"
    assert result3.get("data") == {
        CONF_HOST: TEST_HOST,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: DEFAULT_PORT,
        CONF_USERNAME: TEST_USERNAME,
        PW_TYPE: API,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_smile_config_flow.connect.mock_calls) == 2


async def test_zeroconf_abort_anna_with_existing_config_entries(
    hass: HomeAssistant,
    mock_smile_adam: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test we abort Anna discovery with existing config entries."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DISCOVERY_ANNA,
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "anna_with_adam"


async def test_zeroconf_abort_anna_with_adam(hass: HomeAssistant) -> None:
    """Test we abort Anna discovery when an Adam is also discovered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DISCOVERY_ANNA,
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    flows_in_progress = hass.config_entries.flow.async_progress()
    assert len(flows_in_progress) == 1
    assert flows_in_progress[0]["context"]["product"] == "smile_thermo"

    # Discover Adam, Anna should be aborted and no longer present
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DISCOVERY_ADAM,
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "user"

    flows_in_progress = hass.config_entries.flow.async_progress()
    assert len(flows_in_progress) == 1
    assert flows_in_progress[0]["context"]["product"] == "smile_open_therm"

    # Discover Anna again, Anna should be aborted directly
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DISCOVERY_ANNA,
    )
    assert result3.get("type") == FlowResultType.ABORT
    assert result3.get("reason") == "anna_with_adam"

    # Adam should still be there
    flows_in_progress = hass.config_entries.flow.async_progress()
    assert len(flows_in_progress) == 1
    assert flows_in_progress[0]["context"]["product"] == "smile_open_therm"
