"""Test the my-PV config flow."""

from ipaddress import ip_address
from unittest.mock import patch

from my_pv.exceptions import MyPVAuthenticationError

from homeassistant import config_entries
from homeassistant.components.my_pv.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

MOCK_CONFIG_LOCAL = {
    CONF_HOST: "127.0.0.1",
}

MOCK_CONFIG_LOCAL_AUTH = {
    CONF_PASSWORD: "test-password",
}

MOCK_CONFIG_CLOUD = {
    CONF_SERIAL_NUMBER: "1601500000000000",
    CONF_TOKEN: "my0000000000000000000000000000000000000000000000PV",
}

DHCP_DISCOVERY = DhcpServiceInfo(
    "127.0.0.1",
    macaddress="986d35cabcdef",
    hostname="",
)
ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("127.0.0.1"),
    ip_addresses=[ip_address("127.0.0.1")],
    hostname="mypv_986d35cabcdef.local.",
    name="_mypv._mypv._tcp.local.",
    port=80,
    type="_mypv._tcp.local.",
    properties={
        "vendor": "my-PV",
        "fw_ver": "3.0.8",
        "serialno": "1601500000000000",
        "model": "AC ELWA 2",
    },
)


async def test_step_user(hass: HomeAssistant) -> None:
    """Test we get the menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"


async def test_step_setup_local(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert "setup_local" in result["menu_options"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "setup_local"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_local"
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            return_value=True,
        ),
        # patch(
        #     "homeassistant.components.my_pv.MyPVLocalDevice._connection.fetch_setup",
        #     {}
        # )
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG_LOCAL
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "my-PV None"
        # assert result["result"].unique_id == "01:23:45:67:89:AB"
        # assert result["data"] == MOCK_CONFIG_LOCAL


async def test_step_local_auth(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert "setup_local" in result["menu_options"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "setup_local"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_local"
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            side_effect=MyPVAuthenticationError(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG_LOCAL
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "local_auth"

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG_LOCAL_AUTH
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_step_setup_cloud(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert "setup_cloud" in result["menu_options"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "setup_cloud"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_cloud"
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.my_pv.MyPVCloudDevice.connect",
            return_value=True,
        ),
        # patch(
        #     "homeassistant.components.my_pv.MyPVLocalDevice._connection.fetch_setup",
        #     {}
        # )
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG_CLOUD
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "my-PV AC ELWA 2"
        # assert result["result"].unique_id == "01:23:45:67:89:AB"


async def test_step_dhcp(hass: HomeAssistant) -> None:
    """Test for DHCP discovery that does not requires a password."""

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_DHCP,
            },
            data=DHCP_DISCOVERY,
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "discovery_confirm"

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], [])
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_step_dhcp_auth(hass: HomeAssistant) -> None:
    """Test for DHCP discovery that requires a password."""

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            side_effect=MyPVAuthenticationError(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_DHCP,
            },
            data=DHCP_DISCOVERY,
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "local_auth"

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG_LOCAL_AUTH
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_step_zeroconf(hass: HomeAssistant) -> None:
    """Test for Zeroconf discovery that requires a password."""

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            side_effect=MyPVAuthenticationError(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_ZEROCONF,
            },
            data=ZEROCONF_DISCOVERY,
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "local_auth"

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG_LOCAL_AUTH
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
