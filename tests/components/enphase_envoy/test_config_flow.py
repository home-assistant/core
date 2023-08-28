"""Test the Enphase Envoy config flow."""
from unittest.mock import AsyncMock

from pyenphase import EnvoyAuthenticationError, EnvoyError
import pytest

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.enphase_envoy.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_form(hass: HomeAssistant, config, setup_enphase_envoy) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    assert result2["type"] == "create_entry"
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
    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    assert result2["type"] == "create_entry"
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
    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    assert result2["type"] == "create_entry"
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
    assert result2["type"] == "form"
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
    assert result2["type"] == "form"
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
    assert result2["type"] == "form"
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
            host="1.1.1.1",
            addresses=["1.1.1.1"],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234", "protovers": "3.0.0"},
            type="mock_type",
        ),
    )
    assert result["type"] == "form"
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
    assert result2["type"] == "create_entry"
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
            host="1.1.1.1",
            addresses=["1.1.1.1"],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234", "protovers": "7.0.0"},
            type="mock_type",
        ),
    )
    assert result["type"] == "form"
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
    assert result2["type"] == "create_entry"
    assert result2["title"] == "Envoy 1234"
    assert result2["result"].unique_id == "1234"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "name": "Envoy 1234",
        "username": "test-username",
        "password": "test-password",
    }


async def test_form_host_already_exists(
    hass: HomeAssistant, config_entry, setup_enphase_envoy
) -> None:
    """Test host already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
    )
    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


async def test_zeroconf_serial_already_exists(
    hass: HomeAssistant, config_entry, setup_enphase_envoy
) -> None:
    """Test serial number already exists from zeroconf."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="4.4.4.4",
            addresses=["4.4.4.4"],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234"},
            type="mock_type",
        ),
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"

    assert config_entry.data["host"] == "4.4.4.4"


async def test_zeroconf_serial_already_exists_ignores_ipv6(
    hass: HomeAssistant, config_entry, setup_enphase_envoy
) -> None:
    """Test serial number already exists from zeroconf but the discovery is ipv6."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="fd00::b27c:63bb:cc85:4ea0",
            addresses=["fd00::b27c:63bb:cc85:4ea0"],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234"},
            type="mock_type",
        ),
    )
    assert result["type"] == "abort"
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
            host="1.1.1.1",
            addresses=["1.1.1.1"],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={"serialnum": "1234"},
            type="mock_type",
        ),
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"

    assert config_entry.unique_id == "1234"
    assert config_entry.title == "Envoy 1234"


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
    assert result2["type"] == "abort"
    assert result2["reason"] == "reauth_successful"
