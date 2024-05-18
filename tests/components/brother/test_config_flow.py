"""Define tests for the Brother Printer config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from brother import SnmpError, UnsupportedModelError
import pytest

from homeassistant.components import zeroconf
from homeassistant.components.brother.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import init_integration

from tests.common import MockConfigEntry

CONFIG = {CONF_HOST: "127.0.0.1", CONF_TYPE: "laser"}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.parametrize("host", ["example.local", "127.0.0.1", "2001:db8::1428:57ab"])
async def test_create_entry(
    hass: HomeAssistant, host: str, mock_brother_client: AsyncMock
) -> None:
    """Test that the user step works with printer hostname/IPv4/IPv6."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: host, CONF_TYPE: "laser"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HL-L2340DW 0123456789"
    assert result["data"][CONF_HOST] == host
    assert result["data"][CONF_TYPE] == "laser"


async def test_invalid_hostname(hass: HomeAssistant) -> None:
    """Test invalid hostname in user_input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "invalid/hostname", CONF_TYPE: "laser"},
    )

    assert result["errors"] == {CONF_HOST: "wrong_host"}


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (ConnectionError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (SnmpError("SNMP error"), "snmp_error"),
    ],
)
async def test_errors(
    hass: HomeAssistant, exc: Exception, base_error: str, mock_brother_client: AsyncMock
) -> None:
    """Test connection to host error."""
    mock_brother_client.async_update.side_effect = exc

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["errors"] == {"base": base_error}


async def test_unsupported_model_error(hass: HomeAssistant) -> None:
    """Test unsupported printer model error."""
    with patch(
        "homeassistant.components.brother.Brother.create",
        new=AsyncMock(side_effect=UnsupportedModelError("error")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_model"


async def test_device_exists_abort(
    hass: HomeAssistant,
    mock_brother_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort config flow if Brother printer already configured."""
    await init_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("exc", [ConnectionError, TimeoutError, SnmpError("error")])
async def test_zeroconf_exception(
    hass: HomeAssistant, exc: Exception, mock_brother_client: AsyncMock
) -> None:
    """Test we abort zeroconf flow on exception."""
    mock_brother_client.async_update.side_effect = exc

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="example.local.",
            name="Brother Printer",
            port=None,
            properties={},
            type="mock_type",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_unsupported_model(hass: HomeAssistant) -> None:
    """Test unsupported printer model error."""
    with patch(
        "homeassistant.components.brother.Brother.create",
        new=AsyncMock(side_effect=UnsupportedModelError("error")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address("127.0.0.1"),
                ip_addresses=[ip_address("127.0.0.1")],
                hostname="example.local.",
                name="Brother Printer",
                port=None,
                properties={"product": "MFC-8660DN"},
                type="mock_type",
            ),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_model"


async def test_zeroconf_device_exists_abort(
    hass: HomeAssistant,
    mock_brother_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort zeroconf flow if Brother printer already configured."""
    await init_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="example.local.",
            name="Brother Printer",
            port=None,
            properties={},
            type="mock_type",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert mock_config_entry.data[CONF_HOST] == "127.0.0.1"


async def test_zeroconf_no_probe_existing_device(hass: HomeAssistant) -> None:
    """Test we do not probe the device is the host is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="0123456789", data=CONFIG)
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.brother.Brother.initialize"),
        patch("homeassistant.components.brother.Brother._get_data") as mock_get_data,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address("127.0.0.1"),
                ip_addresses=[ip_address("127.0.0.1")],
                hostname="example.local.",
                name="Brother Printer",
                port=None,
                properties={},
                type="mock_type",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_get_data.mock_calls) == 0


async def test_zeroconf_confirm_create_entry(
    hass: HomeAssistant, mock_brother_client: AsyncMock
) -> None:
    """Test zeroconf confirmation and create config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="example.local.",
            name="Brother Printer",
            port=None,
            properties={},
            type="mock_type",
        ),
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"]["model"] == "HL-L2340DW"
    assert result["description_placeholders"]["serial_number"] == "0123456789"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_TYPE: "laser"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HL-L2340DW 0123456789"
    assert result["data"][CONF_HOST] == "127.0.0.1"
    assert result["data"][CONF_TYPE] == "laser"
