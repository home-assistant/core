"""Test the Plugwise config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

from plugwise.exceptions import (
    ConnectionFailedError,
    InvalidAuthentication,
    PlugwiseException,
)
import pytest

from homeassistant.components import zeroconf
from homeassistant.components.plugwise.const import (
    API,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FLOW_NET,
    FLOW_TYPE,
    PW_TYPE,
)
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SOURCE,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.common import MockConfigEntry

TEST_HOST = "1.1.1.1"
TEST_HOSTNAME = "smileabcdef"
TEST_HOSTNAME2 = "stretchabc"
TEST_PASSWORD = "test_password"
TEST_PORT = 81
TEST_USERNAME = "smile"
TEST_USERNAME2 = "stretch"

TEST_DISCOVERY = zeroconf.ZeroconfServiceInfo(
    host=TEST_HOST,
    hostname=f"{TEST_HOSTNAME}.local.",
    name="mock_name",
    port=DEFAULT_PORT,
    properties={
        "product": "smile",
        "version": "1.2.3",
        "hostname": f"{TEST_HOSTNAME}.local.",
    },
    type="mock_type",
)
TEST_DISCOVERY2 = zeroconf.ZeroconfServiceInfo(
    host=TEST_HOST,
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


@pytest.fixture(name="mock_smile")
def mock_smile():
    """Create a Mock Smile for testing exceptions."""
    with patch(
        "homeassistant.components.plugwise.config_flow.Smile",
    ) as smile_mock:
        smile_mock.PlugwiseException = PlugwiseException
        smile_mock.InvalidAuthentication = InvalidAuthentication
        smile_mock.ConnectionFailedError = ConnectionFailedError
        smile_mock.return_value.connect.return_value = True
        yield smile_mock.return_value


async def test_form_flow_gateway(hass):
    """Test we get the form for Plugwise Gateway product type."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={FLOW_TYPE: FLOW_NET}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user_gateway"


async def test_form(hass):
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_NET}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.plugwise.config_flow.Smile.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.plugwise.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: TEST_HOST, CONF_PASSWORD: TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: DEFAULT_PORT,
        CONF_USERNAME: TEST_USERNAME,
        PW_TYPE: API,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_form(hass):
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DISCOVERY,
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.plugwise.config_flow.Smile.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.plugwise.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: DEFAULT_PORT,
        CONF_USERNAME: TEST_USERNAME,
        PW_TYPE: API,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_stretch_form(hass):
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DISCOVERY2,
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.plugwise.config_flow.Smile.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.plugwise.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: DEFAULT_PORT,
        CONF_USERNAME: TEST_USERNAME2,
        PW_TYPE: API,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_zercoconf_discovery_update_configuration(hass):
    """Test if a discovered device is configured and updated with new host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=CONF_NAME,
        data={CONF_HOST: "0.0.0.0", CONF_PASSWORD: TEST_PASSWORD},
        unique_id=TEST_HOSTNAME,
    )
    entry.add_to_hass(hass)

    assert entry.data[CONF_HOST] == "0.0.0.0"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DISCOVERY,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "1.1.1.1"


async def test_form_username(hass):
    """Test we get the username data back."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_NET}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.plugwise.config_flow.Smile",
    ) as smile_mock, patch(
        "homeassistant.components.plugwise.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        smile_mock.return_value.connect.side_effect = AsyncMock(return_value=True)
        smile_mock.return_value.gateway_id = "abcdefgh12345678"
        smile_mock.return_value.smile_hostname = TEST_HOST
        smile_mock.return_value.smile_name = "Adam"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: TEST_HOST,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_USERNAME: TEST_USERNAME2,
            },
        )

        await hass.async_block_till_done()

        assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result2["data"] == {
            CONF_HOST: TEST_HOST,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: TEST_USERNAME2,
            PW_TYPE: API,
        }

    assert len(mock_setup_entry.mock_calls) == 1

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DISCOVERY,
    )
    assert result3["type"] == RESULT_TYPE_FORM

    with patch(
        "homeassistant.components.plugwise.config_flow.Smile",
    ) as smile_mock, patch(
        "homeassistant.components.plugwise.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        smile_mock.return_value.side_effect = AsyncMock(return_value=True)
        smile_mock.return_value.connect.side_effect = AsyncMock(return_value=True)
        smile_mock.return_value.gateway_id = "abcdefgh12345678"
        smile_mock.return_value.smile_hostname = TEST_HOST
        smile_mock.return_value.smile_name = "Adam"

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            user_input={CONF_PASSWORD: TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert result4["type"] == "abort"
    assert result4["reason"] == "already_configured"


async def test_form_invalid_auth(hass, mock_smile):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_NET}
    )

    mock_smile.connect.side_effect = InvalidAuthentication
    mock_smile.gateway_id = "0a636a4fc1704ab4a24e4f7e37fb187a"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: TEST_HOST, CONF_PASSWORD: TEST_PASSWORD},
    )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass, mock_smile):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_NET}
    )

    mock_smile.connect.side_effect = ConnectionFailedError
    mock_smile.gateway_id = "0a636a4fc1704ab4a24e4f7e37fb187a"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: TEST_HOST, CONF_PASSWORD: TEST_PASSWORD},
    )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect_port(hass, mock_smile):
    """Test we handle cannot connect to port error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_NET}
    )

    mock_smile.connect.side_effect = ConnectionFailedError
    mock_smile.gateway_id = "0a636a4fc1704ab4a24e4f7e37fb187a"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: TEST_HOST,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
        },
    )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_other_problem(hass, mock_smile):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_NET}
    )

    mock_smile.connect.side_effect = TimeoutError
    mock_smile.gateway_id = "0a636a4fc1704ab4a24e4f7e37fb187a"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: TEST_HOST, CONF_PASSWORD: TEST_PASSWORD},
    )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_options_flow_power(hass, mock_smile) -> None:
    """Test config flow options DSMR environments."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=CONF_NAME,
        data={CONF_HOST: TEST_HOST, CONF_PASSWORD: TEST_PASSWORD},
        options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    )

    hass.data[DOMAIN] = {entry.entry_id: {"api": MagicMock(smile_type="power")}}
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.plugwise.async_setup_entry", return_value=True
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_SCAN_INTERVAL: 10}
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {
            CONF_SCAN_INTERVAL: 10,
        }


async def test_options_flow_thermo(hass, mock_smile) -> None:
    """Test config flow options for thermostatic environments."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=CONF_NAME,
        data={CONF_HOST: TEST_HOST, CONF_PASSWORD: TEST_PASSWORD},
        options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    )

    hass.data[DOMAIN] = {entry.entry_id: {"api": MagicMock(smile_type="thermostat")}}
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.plugwise.async_setup_entry", return_value=True
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_SCAN_INTERVAL: 60}
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {
            CONF_SCAN_INTERVAL: 60,
        }
