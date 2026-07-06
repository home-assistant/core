"""Test the my-PV config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from my_pv.exceptions import MyPVAuthenticationError
import pytest

from homeassistant import config_entries
from homeassistant.components.my_pv.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import ELWA2_SERIAL_NUMBER

from tests.common import MockConfigEntry

DHCP_DISCOVERY = DhcpServiceInfo(
    "127.0.0.1",
    macaddress="986d35cabcde",
    hostname="",
)

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("127.0.0.1"),
    ip_addresses=[ip_address("127.0.0.1")],
    hostname=f"my-pv-ac-elwa-2-{ELWA2_SERIAL_NUMBER}.local.",
    name=f"my-pv-ac-elwa-2-{ELWA2_SERIAL_NUMBER}._mypv._tcp.local.",
    port=443,
    type="_mypv._tcp.local.",
    properties={"": None},
)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_user(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if we get the local setup form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "my-PV AC ELWA 2 0000000000"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
    }
    assert result["result"].unique_id == ELWA2_SERIAL_NUMBER


async def test_step_user_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for user configuration that is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_step_user_cannot_connect(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if we get the local setup form with error if we can not connect to device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    mock_my_pv_client.connect.return_value = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_auth(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test we get the authentication form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    mock_my_pv_client.connect.side_effect = MyPVAuthenticationError()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert not result["errors"]

    mock_my_pv_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "my-PV AC ELWA 2 0000000000"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == ELWA2_SERIAL_NUMBER


async def test_step_auth_cannot_connect(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test we get the authentication form with error if we can not connect to device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    mock_my_pv_client.connect.side_effect = MyPVAuthenticationError()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert not result["errors"]

    mock_my_pv_client.connect.return_value = False
    mock_my_pv_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.usefixtures("mock_setup_entry", "mock_my_pv_client")
async def test_step_dhcp(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for DHCP discovery that does not require a password."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_DHCP,
        },
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "my-PV AC ELWA 2 0000000000"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
    }
    assert result["result"].unique_id == ELWA2_SERIAL_NUMBER


async def test_step_dhcp_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for DHCP discovery that is already configured."""
    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.connect.side_effect = MyPVAuthenticationError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_DHCP,
        },
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_step_dhcp_cannot_connect(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for DHCP discovery that can not connect."""

    mock_my_pv_client.connect.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_DHCP,
        },
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_dhcp_auth(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for DHCP discovery that requires a password."""

    mock_my_pv_client.connect.side_effect = MyPVAuthenticationError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_DHCP,
        },
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_auth"
    assert not result["errors"]

    mock_my_pv_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "test-password"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "my-PV AC ELWA 2 0000000000"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == ELWA2_SERIAL_NUMBER


async def test_step_dhcp_auth_wrong_password(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for DHCP discovery with an incorrect password."""

    mock_my_pv_client.connect.side_effect = MyPVAuthenticationError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_DHCP,
        },
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_auth"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "wrong-password"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_auth"
    assert result["errors"]["password"] == "invalid_password"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_zeroconf(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for Zeroconf discovery that requires a password."""

    mock_my_pv_client.connect.side_effect = MyPVAuthenticationError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_ZEROCONF,
        },
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_auth"
    assert not result["errors"]

    mock_my_pv_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "test-password"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "my-PV AC ELWA 2 0000000000"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == ELWA2_SERIAL_NUMBER


async def test_step_zeroconf_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for Zeroconf discovery that is already configured."""
    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.connect.side_effect = MyPVAuthenticationError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_ZEROCONF,
        },
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_step_zeroconf_cannot_connect(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for Zeroconf discovery that can not connect."""

    mock_my_pv_client.connect.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_ZEROCONF,
        },
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_step_zeroconf_wrong_password(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for Zeroconf discovery with an incorrect password."""

    mock_my_pv_client.connect.side_effect = MyPVAuthenticationError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_ZEROCONF,
        },
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_auth"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "wrong-password"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_auth"
    assert result["errors"]["password"] == "invalid_password"
