"""Define tests for the PlayStation 4 config flow."""
from pyps4_2ndscreen.errors import CredentialTimeout
import pytest

from homeassistant import data_entry_flow
from homeassistant.components import ps4
from homeassistant.components.ps4.config_flow import LOCAL_UDP_PORT
from homeassistant.components.ps4.const import (
    DEFAULT_ALIAS,
    DEFAULT_NAME,
    DEFAULT_REGION,
    DOMAIN,
)
from homeassistant.const import (
    CONF_CODE,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_REGION,
    CONF_TOKEN,
)
from homeassistant.util import location

from tests.async_mock import patch
from tests.common import MockConfigEntry

MOCK_TITLE = "PlayStation 4"
MOCK_CODE = 12345678
MOCK_CODE_LEAD_0 = 1234567
MOCK_CODE_LEAD_0_STR = "01234567"
MOCK_CREDS = "000aa000"
MOCK_HOST = "192.0.0.0"
MOCK_HOST_ADDITIONAL = "192.0.0.1"
MOCK_DEVICE = {
    CONF_HOST: MOCK_HOST,
    CONF_NAME: DEFAULT_NAME,
    CONF_REGION: DEFAULT_REGION,
}
MOCK_DEVICE_ADDITIONAL = {
    CONF_HOST: MOCK_HOST_ADDITIONAL,
    CONF_NAME: DEFAULT_NAME,
    CONF_REGION: DEFAULT_REGION,
}
MOCK_CONFIG = {
    CONF_IP_ADDRESS: MOCK_HOST,
    CONF_NAME: DEFAULT_NAME,
    CONF_REGION: DEFAULT_REGION,
    CONF_CODE: MOCK_CODE,
}
MOCK_CONFIG_ADDITIONAL = {
    CONF_IP_ADDRESS: MOCK_HOST_ADDITIONAL,
    CONF_NAME: DEFAULT_NAME,
    CONF_REGION: DEFAULT_REGION,
    CONF_CODE: MOCK_CODE,
}
MOCK_DATA = {CONF_TOKEN: MOCK_CREDS, "devices": [MOCK_DEVICE]}
MOCK_UDP_PORT = int(987)
MOCK_TCP_PORT = int(997)

MOCK_AUTO = {"Config Mode": "Auto Discover"}
MOCK_MANUAL = {"Config Mode": "Manual Entry", CONF_IP_ADDRESS: MOCK_HOST}

MOCK_LOCATION = location.LocationInfo(
    "0.0.0.0",
    "US",
    "United States",
    "CA",
    "California",
    "San Diego",
    "92122",
    "America/Los_Angeles",
    32.8594,
    -117.2073,
    True,
)


@pytest.fixture(name="location_info", autouse=True)
def location_info_fixture():
    """Mock location info."""
    with patch(
        "homeassistant.components.ps4.config_flow.location.async_detect_location_info",
        return_value=MOCK_LOCATION,
    ):
        yield


@pytest.fixture(name="ps4_setup", autouse=True)
def ps4_setup_fixture():
    """Patch ps4 setup entry."""
    with patch(
        "homeassistant.components.ps4.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_full_flow_implementation(hass):
    """Test registering an implementation and flow works."""
    # User Step Started, results in Step Creds
    with patch("pyps4_2ndscreen.Helper.port_bind", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "creds"

    # Step Creds results with form in Step Mode.
    with patch("pyps4_2ndscreen.Helper.get_creds", return_value=MOCK_CREDS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "mode"

    # Step Mode with User Input which is not manual, results in Step Link.
    with patch(
        "pyps4_2ndscreen.Helper.has_devices", return_value=[{"host-ip": MOCK_HOST}]
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_AUTO
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    # User Input results in created entry.
    with patch("pyps4_2ndscreen.Helper.link", return_value=(True, True)), patch(
        "pyps4_2ndscreen.Helper.has_devices", return_value=[{"host-ip": MOCK_HOST}]
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == MOCK_CREDS
    assert result["data"]["devices"] == [MOCK_DEVICE]
    assert result["title"] == MOCK_TITLE


async def test_multiple_flow_implementation(hass):
    """Test multiple device flows."""
    # User Step Started, results in Step Creds
    with patch("pyps4_2ndscreen.Helper.port_bind", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "creds"

    # Step Creds results with form in Step Mode.
    with patch("pyps4_2ndscreen.Helper.get_creds", return_value=MOCK_CREDS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "mode"

    # Step Mode with User Input which is not manual, results in Step Link.
    with patch(
        "pyps4_2ndscreen.Helper.has_devices",
        return_value=[{"host-ip": MOCK_HOST}, {"host-ip": MOCK_HOST_ADDITIONAL}],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_AUTO
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    # User Input results in created entry.
    with patch("pyps4_2ndscreen.Helper.link", return_value=(True, True)), patch(
        "pyps4_2ndscreen.Helper.has_devices",
        return_value=[{"host-ip": MOCK_HOST}, {"host-ip": MOCK_HOST_ADDITIONAL}],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == MOCK_CREDS
    assert result["data"]["devices"] == [MOCK_DEVICE]
    assert result["title"] == MOCK_TITLE

    # Check if entry exists.
    entries = hass.config_entries.async_entries()
    assert len(entries) == 1
    # Check if there is a device config in entry.
    entry_1 = entries[0]
    assert len(entry_1.data["devices"]) == 1

    # Test additional flow.

    # User Step Started, results in Step Mode:
    with patch("pyps4_2ndscreen.Helper.port_bind", return_value=None), patch(
        "pyps4_2ndscreen.Helper.has_devices",
        return_value=[{"host-ip": MOCK_HOST}, {"host-ip": MOCK_HOST_ADDITIONAL}],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "creds"

    # Step Creds results with form in Step Mode.
    with patch("pyps4_2ndscreen.Helper.get_creds", return_value=MOCK_CREDS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "mode"

    # Step Mode with User Input which is not manual, results in Step Link.
    with patch(
        "pyps4_2ndscreen.Helper.has_devices",
        return_value=[{"host-ip": MOCK_HOST}, {"host-ip": MOCK_HOST_ADDITIONAL}],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_AUTO
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    # Step Link
    with patch(
        "pyps4_2ndscreen.Helper.has_devices",
        return_value=[{"host-ip": MOCK_HOST}, {"host-ip": MOCK_HOST_ADDITIONAL}],
    ), patch("pyps4_2ndscreen.Helper.link", return_value=(True, True)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG_ADDITIONAL
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == MOCK_CREDS
    assert len(result["data"]["devices"]) == 1
    assert result["title"] == MOCK_TITLE

    # Check if there are 2 entries.
    entries = hass.config_entries.async_entries()
    assert len(entries) == 2
    # Check if there is device config in the last entry.
    entry_2 = entries[-1]
    assert len(entry_2.data["devices"]) == 1

    # Check that entry 1 is different from entry 2.
    assert entry_1 is not entry_2


async def test_port_bind_abort(hass):
    """Test that flow aborted when cannot bind to ports 987, 997."""
    with patch("pyps4_2ndscreen.Helper.port_bind", return_value=MOCK_UDP_PORT):
        reason = "port_987_bind_error"
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == reason

    with patch("pyps4_2ndscreen.Helper.port_bind", return_value=MOCK_TCP_PORT):
        reason = "port_997_bind_error"
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == reason


async def test_duplicate_abort(hass):
    """Test that Flow aborts when found devices already configured."""
    MockConfigEntry(domain=ps4.DOMAIN, data=MOCK_DATA).add_to_hass(hass)

    with patch("pyps4_2ndscreen.Helper.port_bind", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "creds"

    with patch("pyps4_2ndscreen.Helper.get_creds", return_value=MOCK_CREDS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "mode"

    with patch(
        "pyps4_2ndscreen.Helper.has_devices", return_value=[{"host-ip": MOCK_HOST}]
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_AUTO
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_additional_device(hass):
    """Test that Flow can configure another device."""
    # Mock existing entry.
    entry = MockConfigEntry(domain=ps4.DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with patch("pyps4_2ndscreen.Helper.port_bind", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "creds"

    with patch("pyps4_2ndscreen.Helper.get_creds", return_value=MOCK_CREDS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "mode"

    with patch(
        "pyps4_2ndscreen.Helper.has_devices",
        return_value=[{"host-ip": MOCK_HOST}, {"host-ip": MOCK_HOST_ADDITIONAL}],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_AUTO
        )

    with patch("pyps4_2ndscreen.Helper.link", return_value=(True, True)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG_ADDITIONAL
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == MOCK_CREDS
    assert len(result["data"]["devices"]) == 1
    assert result["title"] == MOCK_TITLE


async def test_0_pin(hass):
    """Test Pin with leading '0' is passed correctly."""
    with patch("pyps4_2ndscreen.Helper.get_creds", return_value=MOCK_CREDS):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "creds"},
            data={},
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "mode"

    with patch(
        "pyps4_2ndscreen.Helper.has_devices", return_value=[{"host-ip": MOCK_HOST}]
    ), patch(
        "homeassistant.components.ps4.config_flow.location.async_detect_location_info",
        return_value=MOCK_LOCATION,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_AUTO
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    mock_config = MOCK_CONFIG
    mock_config[CONF_CODE] = MOCK_CODE_LEAD_0
    with patch(
        "pyps4_2ndscreen.Helper.link", return_value=(True, True)
    ) as mock_call, patch(
        "pyps4_2ndscreen.Helper.has_devices", return_value=[{"host-ip": MOCK_HOST}]
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], mock_config
        )
    mock_call.assert_called_once_with(
        MOCK_HOST, MOCK_CREDS, MOCK_CODE_LEAD_0_STR, DEFAULT_ALIAS, LOCAL_UDP_PORT
    )


async def test_no_devices_found_abort(hass):
    """Test that failure to find devices aborts flow."""
    with patch("pyps4_2ndscreen.Helper.port_bind", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "creds"

    with patch("pyps4_2ndscreen.Helper.get_creds", return_value=MOCK_CREDS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "mode"

    with patch("pyps4_2ndscreen.Helper.has_devices", return_value=[]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_AUTO
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "no_devices_found"


async def test_manual_mode(hass):
    """Test host specified in manual mode is passed to Step Link."""
    with patch("pyps4_2ndscreen.Helper.port_bind", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "creds"

    with patch("pyps4_2ndscreen.Helper.get_creds", return_value=MOCK_CREDS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "mode"

    # Step Mode with User Input: manual, results in Step Link.
    with patch(
        "pyps4_2ndscreen.Helper.has_devices", return_value=[{"host-ip": MOCK_HOST}]
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_MANUAL
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"


async def test_credential_abort(hass):
    """Test that failure to get credentials aborts flow."""
    with patch("pyps4_2ndscreen.Helper.port_bind", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "creds"

    with patch("pyps4_2ndscreen.Helper.get_creds", return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "credential_error"


async def test_credential_timeout(hass):
    """Test that Credential Timeout shows error."""
    with patch("pyps4_2ndscreen.Helper.port_bind", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "creds"

    with patch("pyps4_2ndscreen.Helper.get_creds", side_effect=CredentialTimeout):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "creds"
    assert result["errors"] == {"base": "credential_timeout"}


async def test_wrong_pin_error(hass):
    """Test that incorrect pin throws an error."""
    with patch("pyps4_2ndscreen.Helper.port_bind", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "creds"

    with patch("pyps4_2ndscreen.Helper.get_creds", return_value=MOCK_CREDS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "mode"

    with patch(
        "pyps4_2ndscreen.Helper.has_devices", return_value=[{"host-ip": MOCK_HOST}]
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_AUTO
        )

    with patch("pyps4_2ndscreen.Helper.link", return_value=(True, False)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": "login_failed"}


async def test_device_connection_error(hass):
    """Test that device not connected or on throws an error."""
    with patch("pyps4_2ndscreen.Helper.port_bind", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "creds"

    with patch("pyps4_2ndscreen.Helper.get_creds", return_value=MOCK_CREDS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "mode"

    with patch(
        "pyps4_2ndscreen.Helper.has_devices", return_value=[{"host-ip": MOCK_HOST}]
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_AUTO
        )

    with patch("pyps4_2ndscreen.Helper.link", return_value=(False, True)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_manual_mode_no_ip_error(hass):
    """Test no IP specified in manual mode throws an error."""
    with patch("pyps4_2ndscreen.Helper.port_bind", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "creds"

    with patch("pyps4_2ndscreen.Helper.get_creds", return_value=MOCK_CREDS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "mode"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"Config Mode": "Manual Entry"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "mode"
    assert result["errors"] == {CONF_IP_ADDRESS: "no_ipaddress"}
