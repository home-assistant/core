"""Test the Enphase Envoy config flow."""

from ipaddress import ip_address
import logging
from unittest.mock import AsyncMock

from pyenphase import EnvoyAuthenticationError, EnvoyError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.enphase_envoy.const import DOMAIN, PLATFORMS
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_form(hass: HomeAssistant, config, setup_enphase_envoy) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Envoy 1234"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "name": "Envoy 1234",
        "username": "test-username",
        "password": "test-password",
    }


@pytest.mark.parametrize("serial_number", [None])
async def test_user_no_serial_number(
    hass: HomeAssistant, config, setup_enphase_envoy
) -> None:
    """Test user setup without a serial number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Envoy"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "name": "Envoy",
        "username": "test-username",
        "password": "test-password",
    }


@pytest.mark.parametrize("serial_number", [None])
async def test_user_fetching_serial_fails(
    hass: HomeAssistant, setup_enphase_envoy
) -> None:
    """Test user setup without a serial number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Envoy"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "name": "Envoy",
        "username": "test-username",
        "password": "test-password",
    }


@pytest.mark.parametrize(
    "mock_authenticate",
    [
        AsyncMock(side_effect=EnvoyAuthenticationError("test")),
    ],
)
async def test_form_invalid_auth(hass: HomeAssistant, setup_enphase_envoy) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


@pytest.mark.parametrize(
    "mock_setup",
    [AsyncMock(side_effect=EnvoyError)],
)
async def test_form_cannot_connect(hass: HomeAssistant, setup_enphase_envoy) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    "mock_setup",
    [AsyncMock(side_effect=ValueError)],
)
async def test_form_unknown_error(hass: HomeAssistant, setup_enphase_envoy) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


def _get_schema_default(schema, key_name):
    """Iterate schema to find a key."""
    for schema_key in schema:
        if schema_key == key_name:
            return schema_key.default()
    raise KeyError(f"{key_name} not found in schema")


async def test_zeroconf_pre_token_firmware(
    hass: HomeAssistant, setup_enphase_envoy
) -> None:
    """Test we can setup from zeroconf."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234", "protovers": "3.0.0"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    assert _get_schema_default(result["data_schema"].schema, "username") == "installer"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Envoy 1234"
    assert result2["result"].unique_id == "1234"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "name": "Envoy 1234",
        "username": "test-username",
        "password": "test-password",
    }


async def test_zeroconf_token_firmware(
    hass: HomeAssistant, setup_enphase_envoy
) -> None:
    """Test we can setup from zeroconf."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234", "protovers": "7.0.0"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert _get_schema_default(result["data_schema"].schema, "username") == ""

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Envoy 1234"
    assert result2["result"].unique_id == "1234"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "name": "Envoy 1234",
        "username": "test-username",
        "password": "test-password",
    }


@pytest.mark.parametrize(
    "mock_authenticate",
    [
        AsyncMock(
            side_effect=[
                None,
                EnvoyAuthenticationError("fail authentication"),
                None,
            ]
        ),
    ],
)
async def test_form_host_already_exists(
    hass: HomeAssistant, config_entry, setup_enphase_envoy
) -> None:
    """Test changing credentials for existing host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # existing config
    assert config_entry.data["host"] == "1.1.1.1"
    assert config_entry.data["username"] == "test-username"
    assert config_entry.data["password"] == "test-password"

    # mock failing authentication on first try
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.2",
            "username": "test-username",
            "password": "wrong-password",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    # still original config after failure
    assert config_entry.data["host"] == "1.1.1.1"
    assert config_entry.data["username"] == "test-username"
    assert config_entry.data["password"] == "test-password"

    # mock successful authentication and update of credentials
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.2",
            "username": "test-username",
            "password": "changed-password",
        },
    )
    await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"

    # updated config with new ip and changed pw
    assert config_entry.data["host"] == "1.1.1.2"
    assert config_entry.data["username"] == "test-username"
    assert config_entry.data["password"] == "changed-password"


async def test_zeroconf_serial_already_exists(
    hass: HomeAssistant,
    config_entry,
    setup_enphase_envoy,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test serial number already exists from zeroconf."""
    _LOGGER.setLevel(logging.DEBUG)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("4.4.4.4"),
            ip_addresses=[ip_address("4.4.4.4")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234"},
            type="mock_type",
        ),
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.data["host"] == "4.4.4.4"
    assert "Zeroconf ip 4 processing 4.4.4.4, current hosts: {'1.1.1.1'}" in caplog.text


async def test_zeroconf_serial_already_exists_ignores_ipv6(
    hass: HomeAssistant, config_entry, setup_enphase_envoy
) -> None:
    """Test serial number already exists from zeroconf but the discovery is ipv6."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
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

    assert config_entry.data["host"] == "1.1.1.1"


@pytest.mark.parametrize("serial_number", [None])
async def test_zeroconf_host_already_exists(
    hass: HomeAssistant, config_entry, setup_enphase_envoy
) -> None:
    """Test hosts already exists from zeroconf."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234"},
            type="mock_type",
        ),
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.unique_id == "1234"
    assert config_entry.title == "Envoy 1234"


async def test_zero_conf_while_form(
    hass: HomeAssistant, config_entry, setup_enphase_envoy
) -> None:
    """Test zeroconf while form is active."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234", "protovers": "7.0.1"},
            type="mock_type",
        ),
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data["host"] == "1.1.1.1"
    assert config_entry.unique_id == "1234"
    assert config_entry.title == "Envoy 1234"


async def test_zero_conf_second_envoy_while_form(
    hass: HomeAssistant, config_entry, setup_enphase_envoy
) -> None:
    """Test zeroconf while form is active."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("4.4.4.4"),
            ip_addresses=[ip_address("4.4.4.4")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "4321", "protovers": "7.0.1"},
            type="mock_type",
        ),
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert config_entry.data["host"] == "1.1.1.1"
    assert config_entry.unique_id == "1234"
    assert config_entry.title == "Envoy 1234"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            "host": "4.4.4.4",
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Envoy 4321"
    assert result3["result"].unique_id == "4321"

    result4 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()
    assert result4["type"] is FlowResultType.ABORT


async def test_zero_conf_malformed_serial_property(
    hass: HomeAssistant, config_entry, setup_enphase_envoy
) -> None:
    """Test malformed zeroconf properties."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with pytest.raises(KeyError) as ex:
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address("1.1.1.1"),
                ip_addresses=[ip_address("1.1.1.1")],
                hostname="mock_hostname",
                name="mock_name",
                port=None,
                properties={"serilnum": "1234", "protovers": "7.1.2"},
                type="mock_type",
            ),
        )
        await hass.async_block_till_done()
    assert "serialnum" in str(ex.value)

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.ABORT


async def test_zero_conf_malformed_serial(
    hass: HomeAssistant, config_entry, setup_enphase_envoy
) -> None:
    """Test malformed zeroconf properties."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "12%4", "protovers": "7.1.2"},
            type="mock_type",
        ),
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Envoy 12%4"


async def test_zero_conf_malformed_fw_property(
    hass: HomeAssistant, config_entry, setup_enphase_envoy
) -> None:
    """Test malformed zeroconf property."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234", "protvers": "7.1.2"},
            type="mock_type",
        ),
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data["host"] == "1.1.1.1"
    assert config_entry.unique_id == "1234"
    assert config_entry.title == "Envoy 1234"


async def test_zero_conf_old_blank_entry(
    hass: HomeAssistant, setup_enphase_envoy
) -> None:
    """Test re-using old blank entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "username": "",
            "password": "",
            "name": "unknown",
        },
        unique_id=None,
        title="Envoy",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1"), ip_address("1.1.1.2")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234", "protovers": "7.1.2"},
            type="mock_type",
        ),
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.data["host"] == "1.1.1.1"
    assert entry.unique_id == "1234"
    assert entry.title == "Envoy 1234"


async def test_reauth(hass: HomeAssistant, config_entry, setup_enphase_envoy) -> None:
    """Test we reauth auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": config_entry.unique_id,
            "entry_id": config_entry.entry_id,
        },
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_reconfigure(
    hass: HomeAssistant, config_entry, setup_enphase_envoy
) -> None:
    """Test we can reconfiger the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": config_entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # original entry
    assert config_entry.data["host"] == "1.1.1.1"
    assert config_entry.data["username"] == "test-username"
    assert config_entry.data["password"] == "test-password"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.2",
            "username": "test-username2",
            "password": "test-password2",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"

    # changed entry
    assert config_entry.data["host"] == "1.1.1.2"
    assert config_entry.data["username"] == "test-username2"
    assert config_entry.data["password"] == "test-password2"


async def test_reconfigure_nochange(
    hass: HomeAssistant, config_entry, setup_enphase_envoy
) -> None:
    """Test we get the reconfigure form and apply nochange."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": config_entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # original entry
    assert config_entry.data["host"] == "1.1.1.1"
    assert config_entry.data["username"] == "test-username"
    assert config_entry.data["password"] == "test-password"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"

    # unchanged original entry
    assert config_entry.data["host"] == "1.1.1.1"
    assert config_entry.data["username"] == "test-username"
    assert config_entry.data["password"] == "test-password"


async def test_reconfigure_otherenvoy(
    hass: HomeAssistant, config_entry, setup_enphase_envoy, mock_envoy
) -> None:
    """Test entering ip of other envoy and prevent changing it based on serial."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": config_entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # let mock return different serial from first time, sim it's other one on changed ip
    mock_envoy.serial_number = "45678"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.2",
            "username": "test-username",
            "password": "new-password",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unexpected_envoy"}

    # entry should still be original entry
    assert config_entry.data["host"] == "1.1.1.1"
    assert config_entry.data["username"] == "test-username"
    assert config_entry.data["password"] == "test-password"

    # set serial back to original to finsich flow
    mock_envoy.serial_number = "1234"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "new-password",
        },
    )

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reconfigure_successful"

    # updated original entry
    assert config_entry.data["host"] == "1.1.1.1"
    assert config_entry.data["username"] == "test-username"
    assert config_entry.data["password"] == "new-password"


@pytest.mark.parametrize(
    "mock_authenticate",
    [
        AsyncMock(
            side_effect=[
                None,
                EnvoyAuthenticationError("fail authentication"),
                EnvoyError("cannot_connect"),
                Exception("Unexpected exception"),
                None,
            ]
        ),
    ],
)
async def test_reconfigure_auth_failure(
    hass: HomeAssistant, config_entry, setup_enphase_envoy
) -> None:
    """Test changing credentials for existing host with auth failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": config_entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # existing config
    assert config_entry.data["host"] == "1.1.1.1"
    assert config_entry.data["username"] == "test-username"
    assert config_entry.data["password"] == "test-password"

    # mock failing authentication on first try
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.2",
            "username": "test-username",
            "password": "wrong-password",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    # still original config after failure
    assert config_entry.data["host"] == "1.1.1.1"
    assert config_entry.data["username"] == "test-username"
    assert config_entry.data["password"] == "test-password"

    # mock failing authentication on first try
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.2",
            "username": "new-username",
            "password": "wrong-password",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    # still original config after failure
    assert config_entry.data["host"] == "1.1.1.1"
    assert config_entry.data["username"] == "test-username"
    assert config_entry.data["password"] == "test-password"

    # mock failing authentication on first try
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.2",
            "username": "other-username",
            "password": "test-password",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    # still original config after failure
    assert config_entry.data["host"] == "1.1.1.1"
    assert config_entry.data["username"] == "test-username"
    assert config_entry.data["password"] == "test-password"

    # mock successful authentication and update of credentials
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.2",
            "username": "test-username",
            "password": "changed-password",
        },
    )
    await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reconfigure_successful"

    # updated config with new ip and changed pw
    assert config_entry.data["host"] == "1.1.1.2"
    assert config_entry.data["username"] == "test-username"
    assert config_entry.data["password"] == "changed-password"


async def test_reconfigure_change_ip_to_existing(
    hass: HomeAssistant, config_entry, setup_enphase_envoy
) -> None:
    """Test reconfiguration to existing entry with same ip does not harm existing one."""
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
    assert other_entry.data["host"] == "1.1.1.2"
    assert other_entry.data["username"] == "other-username"
    assert other_entry.data["password"] == "other-password"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": config_entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # original entry
    assert config_entry.data["host"] == "1.1.1.1"
    assert config_entry.data["username"] == "test-username"
    assert config_entry.data["password"] == "test-password"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.2",
            "username": "test-username",
            "password": "test-password2",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"

    # updated entry
    assert config_entry.data["host"] == "1.1.1.2"
    assert config_entry.data["username"] == "test-username"
    assert config_entry.data["password"] == "test-password2"

    # unchanged other entry
    assert other_entry.data["host"] == "1.1.1.2"
    assert other_entry.data["username"] == "other-username"
    assert other_entry.data["password"] == "other-password"


async def test_platforms(snapshot: SnapshotAssertion) -> None:
    """Test if platform list changed and requires more tests."""
    assert snapshot == PLATFORMS
