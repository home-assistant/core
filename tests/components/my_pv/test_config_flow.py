"""Test the my-PV config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from my_pv.exceptions import MyPVAuthenticationError
import pytest

from homeassistant import config_entries
from homeassistant.components.my_pv.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import BaseServiceInfo, FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import ELWA2_SERIAL_NUMBER

from tests.common import MockConfigEntry

DHCP_DISCOVERY = DhcpServiceInfo(
    "127.0.0.1",
    macaddress="986d35cabcde",
    hostname=f"my-pv-ac-elwa-2-{ELWA2_SERIAL_NUMBER}.local.",
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


@pytest.mark.usefixtures("mock_my_pv_client", "mock_setup_entry")
async def test_step_user(
    hass: HomeAssistant,
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


@pytest.mark.usefixtures("mock_my_pv_client")
async def test_step_user_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
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

    mock_my_pv_client.connect.return_value = True

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

    mock_my_pv_client.connect.return_value = True

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


@pytest.mark.usefixtures("mock_setup_entry", "mock_my_pv_client")
async def test_step_dhcp(
    hass: HomeAssistant,
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


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (
            config_entries.SOURCE_DHCP,
            DHCP_DISCOVERY,
        ),
        (
            config_entries.SOURCE_ZEROCONF,
            ZEROCONF_DISCOVERY,
        ),
    ],
)
@pytest.mark.usefixtures("mock_my_pv_client")
async def test_step_discovery_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    source: str,
    data: BaseServiceInfo,
) -> None:
    """Test for discovery that is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": source,
        },
        data=data,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (
            config_entries.SOURCE_DHCP,
            DHCP_DISCOVERY,
        ),
        (
            config_entries.SOURCE_ZEROCONF,
            ZEROCONF_DISCOVERY,
        ),
    ],
)
async def test_step_discovery_cannot_connect(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
    source: str,
    data: BaseServiceInfo,
) -> None:
    """Test for discovery that can not connect."""

    mock_my_pv_client.connect.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": source,
        },
        data=data,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (
            config_entries.SOURCE_DHCP,
            DHCP_DISCOVERY,
        ),
        (
            config_entries.SOURCE_ZEROCONF,
            ZEROCONF_DISCOVERY,
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_discovery_auth(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
    source: str,
    data: BaseServiceInfo,
) -> None:
    """Test for discovery that requires a password."""

    mock_my_pv_client.connect.side_effect = MyPVAuthenticationError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": source,
        },
        data=data,
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


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (
            config_entries.SOURCE_DHCP,
            DHCP_DISCOVERY,
        ),
        (
            config_entries.SOURCE_ZEROCONF,
            ZEROCONF_DISCOVERY,
        ),
    ],
)
async def test_step_discovery_auth_wrong_password(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
    source: str,
    data: BaseServiceInfo,
) -> None:
    """Test for discovery with an incorrect password."""

    mock_my_pv_client.connect.side_effect = MyPVAuthenticationError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": source,
        },
        data=data,
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

    mock_my_pv_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "test-password"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "my-PV AC ELWA 2 0000000000"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == ELWA2_SERIAL_NUMBER
