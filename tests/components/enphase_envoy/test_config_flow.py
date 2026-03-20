"""Test the Enphase Envoy config flow."""

from ipaddress import ip_address
import logging
from unittest.mock import AsyncMock

from pyenphase import EnvoyAuthenticationError, EnvoyError, EnvoyTokenAuth
import pytest

from homeassistant.components.enphase_envoy.const import (
    CONF_MANUAL_TOKEN,
    DOMAIN,
    OPTION_DIAGNOSTICS_INCLUDE_FIXTURES,
    OPTION_DIAGNOSTICS_INCLUDE_FIXTURES_DEFAULT_VALUE,
    OPTION_DISABLE_KEEP_ALIVE,
    OPTION_DISABLE_KEEP_ALIVE_DEFAULT_VALUE,
)
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import envoy_token, setup_integration

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Envoy 1234"
    assert result["result"].unique_id == "1234"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_NAME: "Envoy 1234",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_MANUAL_TOKEN: False,
        CONF_TOKEN: mock_envoy.auth.token,
    }


async def test_user_no_serial_number(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test user setup without a serial number."""
    mock_envoy.serial_number = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Envoy"
    assert result["result"].unique_id is None
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_NAME: "Envoy",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_MANUAL_TOKEN: False,
        # mock always fills token
        CONF_TOKEN: mock_envoy.auth.token,
    }


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (EnvoyAuthenticationError("fail authentication"), "invalid_auth"),
        (EnvoyError, "cannot_connect"),
        (Exception, "unknown"),
        (ValueError, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle form errors."""
    mock_envoy.setup.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_envoy.setup.side_effect = None
    # mock successful authentication and update of credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


def _get_schema_default(schema, key_name):
    """Iterate schema to find a key."""
    for schema_key in schema:
        if schema_key == key_name:
            return schema_key.default()
    raise KeyError(f"{key_name} not found in schema")


@pytest.mark.parametrize(
    ("version", "schema_username"),
    [
        ("7.0.0", ""),
        ("3.0.0", "installer"),
    ],
)
async def test_zeroconf(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
    version: str,
    schema_username: str,
) -> None:
    """Test we can setup from zeroconf."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234", "protovers": version},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert (
        _get_schema_default(result["data_schema"].schema, CONF_USERNAME)
        == schema_username
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Envoy 1234"
    assert result2["result"].unique_id == "1234"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_NAME: "Envoy 1234",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_MANUAL_TOKEN: False,
        CONF_TOKEN: mock_envoy.auth.token,
    }


async def test_form_host_already_exists(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test changing credentials for existing host."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # existing config
    assert config_entry.data[CONF_HOST] == "1.1.1.1"
    assert config_entry.data[CONF_USERNAME] == "test-username"
    assert config_entry.data[CONF_PASSWORD] == "test-password"

    mock_envoy.authenticate.side_effect = EnvoyAuthenticationError(
        "fail authentication"
    )

    # mock failing authentication on first try
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.2",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "wrong-password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_envoy.authenticate.side_effect = None

    # still original config after failure
    assert config_entry.data[CONF_HOST] == "1.1.1.1"
    assert config_entry.data[CONF_USERNAME] == "test-username"
    assert config_entry.data[CONF_PASSWORD] == "test-password"

    # mock successful authentication and update of credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.2",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "changed-password",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    # updated config with new ip and changed pw
    assert config_entry.data[CONF_HOST] == "1.1.1.2"
    assert config_entry.data[CONF_USERNAME] == "test-username"
    assert config_entry.data[CONF_PASSWORD] == "changed-password"


async def test_zeroconf_serial_already_exists(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test serial number already exists from zeroconf."""
    _LOGGER.setLevel(logging.DEBUG)
    await setup_integration(hass, config_entry)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("4.4.4.4"),
            ip_addresses=[ip_address("4.4.4.4")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.data[CONF_HOST] == "4.4.4.4"
    assert "Zeroconf ip 4 processing 4.4.4.4, current hosts: {'1.1.1.1'}" in caplog.text


async def test_zeroconf_serial_already_exists_ignores_ipv6(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test serial number already exists from zeroconf but the discovery is ipv6."""
    await setup_integration(hass, config_entry)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("fd00::b27c:63bb:cc85:4ea0"),
            ip_addresses=[ip_address("fd00::b27c:63bb:cc85:4ea0")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234"},
            type="mock_type",
        ),
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_ipv4_address"

    assert config_entry.data[CONF_HOST] == "1.1.1.1"


async def test_zeroconf_host_already_exists(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test hosts already exists from zeroconf."""
    mock_envoy.serial_number = None
    await setup_integration(hass, config_entry)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.unique_id == "1234"
    assert config_entry.title == "Envoy 1234"


async def test_zero_conf_while_form(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test zeroconf while form is active."""
    await setup_integration(hass, config_entry)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234", "protovers": "7.0.1"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == "1.1.1.1"
    assert config_entry.unique_id == "1234"
    assert config_entry.title == "Envoy 1234"


async def test_zero_conf_second_envoy_while_form(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test zeroconf while form is active."""
    await setup_integration(hass, config_entry)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("4.4.4.4"),
            ip_addresses=[ip_address("4.4.4.4")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "4321", "protovers": "7.0.1"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert config_entry.data[CONF_HOST] == "1.1.1.1"
    assert config_entry.unique_id == "1234"
    assert config_entry.title == "Envoy 1234"

    result2 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_HOST: "4.4.4.4",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Envoy 4321"
    assert result2["result"].unique_id == "4321"

    result4 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result4["type"] is FlowResultType.ABORT


async def test_zero_conf_old_blank_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test reusing old blank entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_NAME: "unknown",
        },
        unique_id=None,
        title="Envoy",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1"), ip_address("1.1.1.2")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234", "protovers": "7.1.2"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.data[CONF_HOST] == "1.1.1.1"
    assert entry.unique_id == "1234"
    assert entry.title == "Envoy 1234"


async def test_zero_conf_old_blank_entry_standard_title(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test reusing old blank entry was Envoy as title."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_NAME: "unknown",
        },
        unique_id=None,
        title="Envoy",
    )
    entry.add_to_hass(hass)
    # test if shorthand title Envoy gets serial appended
    hass.config_entries.async_update_entry(entry, title="Envoy")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1"), ip_address("1.1.1.2")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234", "protovers": "7.1.2"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.data[CONF_HOST] == "1.1.1.1"
    assert entry.unique_id == "1234"
    assert entry.title == "Envoy 1234"


async def test_zero_conf_old_blank_entry_user_title(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test reusing old blank entry with user title."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_NAME: "unknown",
        },
        unique_id=None,
        title="Envoy",
    )
    entry.add_to_hass(hass)
    # set user title on entry
    hass.config_entries.async_update_entry(entry, title="Envoy Backyard")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1"), ip_address("1.1.1.2")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234", "protovers": "7.1.2"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.data[CONF_HOST] == "1.1.1.1"
    assert entry.unique_id == "1234"
    assert entry.title == "Envoy Backyard"


async def test_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test we reauth auth."""
    await setup_integration(hass, config_entry)
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_options_default(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test we can configure options."""
    await setup_integration(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        OPTION_DIAGNOSTICS_INCLUDE_FIXTURES: OPTION_DIAGNOSTICS_INCLUDE_FIXTURES_DEFAULT_VALUE,
        OPTION_DISABLE_KEEP_ALIVE: OPTION_DISABLE_KEEP_ALIVE_DEFAULT_VALUE,
    }


async def test_options_set(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test we can configure options."""
    await setup_integration(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            OPTION_DIAGNOSTICS_INCLUDE_FIXTURES: True,
            OPTION_DISABLE_KEEP_ALIVE: True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        OPTION_DIAGNOSTICS_INCLUDE_FIXTURES: True,
        OPTION_DISABLE_KEEP_ALIVE: True,
    }


async def test_reconfigure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test we can reconfiger the entry."""
    await setup_integration(hass, config_entry)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # original entry
    assert config_entry.data[CONF_HOST] == "1.1.1.1"
    assert config_entry.data[CONF_USERNAME] == "test-username"
    assert config_entry.data[CONF_PASSWORD] == "test-password"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.2",
            CONF_USERNAME: "test-username2",
            CONF_PASSWORD: "test-password2",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # changed entry
    assert config_entry.data[CONF_HOST] == "1.1.1.2"
    assert config_entry.data[CONF_USERNAME] == "test-username2"
    assert config_entry.data[CONF_PASSWORD] == "test-password2"


async def test_reconfigure_nochange(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test we get the reconfigure form and apply nochange."""
    await setup_integration(hass, config_entry)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # original entry
    assert config_entry.data[CONF_HOST] == "1.1.1.1"
    assert config_entry.data[CONF_USERNAME] == "test-username"
    assert config_entry.data[CONF_PASSWORD] == "test-password"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # unchanged original entry
    assert config_entry.data[CONF_HOST] == "1.1.1.1"
    assert config_entry.data[CONF_USERNAME] == "test-username"
    assert config_entry.data[CONF_PASSWORD] == "test-password"


async def test_reconfigure_otherenvoy(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test entering ip of other envoy and prevent changing it based on serial."""
    await setup_integration(hass, config_entry)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # let mock return different serial from first time, sim it's other one on changed ip
    mock_envoy.serial_number = "45678"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.2",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"

    # entry should still be original entry
    assert config_entry.data[CONF_HOST] == "1.1.1.1"
    assert config_entry.data[CONF_USERNAME] == "test-username"
    assert config_entry.data[CONF_PASSWORD] == "test-password"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (EnvoyAuthenticationError("fail authentication"), "invalid_auth"),
        (EnvoyError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_reconfigure_auth_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test changing credentials for existing host with auth failure."""
    await setup_integration(hass, config_entry)

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # existing config
    assert config_entry.data[CONF_HOST] == "1.1.1.1"
    assert config_entry.data[CONF_USERNAME] == "test-username"
    assert config_entry.data[CONF_PASSWORD] == "test-password"

    mock_envoy.authenticate.side_effect = exception

    # mock failing authentication on first try
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.2",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "wrong-password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_envoy.authenticate.side_effect = None
    # mock successful authentication and update of credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.2",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "changed-password",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # updated config with new ip and changed pw
    assert config_entry.data[CONF_HOST] == "1.1.1.2"
    assert config_entry.data[CONF_USERNAME] == "test-username"
    assert config_entry.data[CONF_PASSWORD] == "changed-password"


async def test_reconfigure_change_ip_to_existing(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test reconfiguration to existing entry with same ip does not harm existing one."""
    await setup_integration(hass, config_entry)
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="65432155aaddb2007c5f6602e0c38e72",
        title="Envoy 654321",
        unique_id="654321",
        data={
            CONF_HOST: "1.1.1.2",
            CONF_NAME: "Envoy 654321",
            CONF_USERNAME: "other-username",
            CONF_PASSWORD: "other-password",
        },
    )
    other_entry.add_to_hass(hass)

    # original other entry
    assert other_entry.data[CONF_HOST] == "1.1.1.2"
    assert other_entry.data[CONF_USERNAME] == "other-username"
    assert other_entry.data[CONF_PASSWORD] == "other-password"

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # original entry
    assert config_entry.data[CONF_HOST] == "1.1.1.1"
    assert config_entry.data[CONF_USERNAME] == "test-username"
    assert config_entry.data[CONF_PASSWORD] == "test-password"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.2",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password2",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # updated entry
    assert config_entry.data[CONF_HOST] == "1.1.1.2"
    assert config_entry.data[CONF_USERNAME] == "test-username"
    assert config_entry.data[CONF_PASSWORD] == "test-password2"

    # unchanged other entry
    assert other_entry.data[CONF_HOST] == "1.1.1.2"
    assert other_entry.data[CONF_USERNAME] == "other-username"
    assert other_entry.data[CONF_PASSWORD] == "other-password"


async def test_form_configure_manual_token(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test user step selecting to use manual token entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # user opts for manual token entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_MANUAL_TOKEN: True,
        },
    )
    await hass.async_block_till_done()
    # no config update only form mode switch
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # in manual token mode user enters host, token and leaves manual_token on
    token = envoy_token()
    mock_envoy.auth = EnvoyTokenAuth("127.0.0.1", token=token, envoy_serial="1234")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_TOKEN: token, CONF_MANUAL_TOKEN: True},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Envoy 1234"
    assert result["result"].unique_id == "1234"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_NAME: "Envoy 1234",
        CONF_MANUAL_TOKEN: True,
        CONF_TOKEN: token,
    }


async def test_form_switch_between_token_modes(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test user step selecting to use automatic token entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # user opts for manual token entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_MANUAL_TOKEN: True,
        },
    )
    await hass.async_block_till_done()
    # no config update only form mode switch
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # in manual token mode user opts to switch back to automatic_token
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_MANUAL_TOKEN: False},
    )
    await hass.async_block_till_done()
    # no config update only form mode switch
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # user enters credentials and leaves manual_token off
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_MANUAL_TOKEN: False,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Envoy 1234"
    assert result["result"].unique_id == "1234"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_NAME: "Envoy 1234",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_MANUAL_TOKEN: False,
        # in auto mode the verification will retrieve token from envoy
        CONF_TOKEN: mock_envoy.auth.token,
    }


async def test_reauth_switch_to_manual_token(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test reauth switch to manual token mode."""
    await setup_integration(hass, config_entry)
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    # user opts to switch to manual token
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_MANUAL_TOKEN: True,
        },
    )
    await hass.async_block_till_done()
    # no config update only form mode switch
    assert result2["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    # user enters token
    token = envoy_token()
    mock_envoy.auth = EnvoyTokenAuth("127.0.0.1", token=token, envoy_serial="1234")

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_TOKEN: token,
            CONF_MANUAL_TOKEN: True,
        },
    )
    await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
    assert config_entry.data[CONF_HOST] == "1.1.1.1"
    assert config_entry.data[CONF_TOKEN] == token
    assert config_entry.data[CONF_MANUAL_TOKEN]


@pytest.mark.parametrize(
    ("config_entry"),
    [("manual")],
    indirect=True,
)
async def test_reauth_manual_token(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test reauth in manual token mode."""
    await setup_integration(hass, config_entry)
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    # user updates manual token
    next_token = envoy_token(300)
    mock_envoy.auth = EnvoyTokenAuth("127.0.0.1", token=next_token, envoy_serial="1234")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: next_token,
            CONF_MANUAL_TOKEN: True,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert config_entry.data[CONF_MANUAL_TOKEN]
    assert config_entry.data[CONF_TOKEN] == next_token


@pytest.mark.parametrize(
    ("config_entry"),
    [("auto")],
    indirect=True,
)
async def test_reconfigure_switch_to_manual_token(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
) -> None:
    """Test reconfigure form switching from automatic to manual token entry."""
    await setup_integration(hass, config_entry)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # user input to switch to manual token entry
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_MANUAL_TOKEN: True},
    )
    await hass.async_block_till_done()
    # no config update, only form mode switch
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reconfigure"
    assert result2["errors"] == {}

    # in manual token mode user enters host, token and manual_token option
    token = envoy_token()
    mock_envoy.auth = EnvoyTokenAuth("127.0.0.1", token=token, envoy_serial="1234")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_TOKEN: token, CONF_MANUAL_TOKEN: True},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Now we should have token and manual_token mode on
    assert config_entry.data[CONF_HOST] == "1.1.1.1"
    assert config_entry.data[CONF_USERNAME] == ""
    assert config_entry.data[CONF_PASSWORD] == ""
    assert config_entry.data[CONF_TOKEN] == token
    assert config_entry.data[CONF_MANUAL_TOKEN]


@pytest.mark.parametrize(
    ("config_entry"),
    [("manual")],
    indirect=True,
)
async def test_reconfigure_manual_token(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure in manual token mode."""
    await setup_integration(hass, config_entry)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # user input to update manual token with token error
    next_token = envoy_token(300)
    wrong_token = "wrongtoken"
    mock_envoy.auth = EnvoyTokenAuth(
        "127.0.0.1", token=wrong_token, envoy_serial="1234"
    )
    mock_envoy.authenticate.side_effect = EnvoyAuthenticationError("Failing test")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_MANUAL_TOKEN: True, CONF_TOKEN: wrong_token},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "invalid_auth"}

    # user input to update manual token
    mock_envoy.auth = EnvoyTokenAuth("127.0.0.1", token=next_token, envoy_serial="1234")
    mock_envoy.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_MANUAL_TOKEN: True, CONF_TOKEN: next_token},
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert config_entry.data[CONF_HOST] == "1.1.1.1"
    assert config_entry.data[CONF_USERNAME] == ""
    assert config_entry.data[CONF_PASSWORD] == ""
    assert config_entry.data[CONF_TOKEN] == next_token
    assert config_entry.data[CONF_MANUAL_TOKEN]


@pytest.mark.parametrize(
    ("config_entry"),
    [("manual")],
    indirect=True,
)
async def test_reconfigure_switch_from_token(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure switching back to automatic token mode."""
    await setup_integration(hass, config_entry)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # user input to switch from manual to automatic token entry
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_MANUAL_TOKEN: False},
    )

    await hass.async_block_till_done()
    # no config update, only switch to other form mode
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reconfigure"
    assert result2["errors"] == {}

    # user updates username & pw
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username1",
            CONF_PASSWORD: "test-password2",
        },
    )
    await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reconfigure_successful"

    # # token should be automatic again and manual_token false
    assert config_entry.data[CONF_HOST] == "1.1.1.1"
    assert config_entry.data[CONF_USERNAME] == "test-username1"
    assert config_entry.data[CONF_PASSWORD] == "test-password2"
    assert config_entry.data[CONF_TOKEN] == mock_envoy.auth.token
    assert not config_entry.data[CONF_MANUAL_TOKEN]
