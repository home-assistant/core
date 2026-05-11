"""Test the my-PV config flow."""

from ipaddress import ip_address
from unittest.mock import patch

from my_pv.exceptions import MyPVAuthenticationError

from homeassistant import config_entries
from homeassistant.components.my_pv.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

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
    """Test if we get the local setup form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.serial_number",
            "1601500000000000",
        ),
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.model",
            "AC ELWA 2",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "127.0.0.1",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "my-PV AC ELWA 2"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
    }
    assert result["result"].unique_id == "1601500000000000"


async def test_step_auth(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            side_effect=MyPVAuthenticationError(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "127.0.0.1",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert not result["errors"]

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.serial_number",
            "1601500000000000",
        ),
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.model",
            "AC ELWA 2",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "my-PV AC ELWA 2"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == "1601500000000000"


async def test_step_dhcp(hass: HomeAssistant) -> None:
    """Test for DHCP discovery that does not require a password."""

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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert not result["errors"]

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.serial_number",
            "1601500000000000",
        ),
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.model",
            "AC ELWA 2",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "my-PV AC ELWA 2"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
    }
    assert result["result"].unique_id == "1601500000000000"


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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_auth"
    assert not result["errors"]

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.serial_number",
            "1601500000000000",
        ),
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.model",
            "AC ELWA 2",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "test-password"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "my-PV AC ELWA 2"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == "1601500000000000"


async def test_step_dhcp_auth_wrong_password(hass: HomeAssistant) -> None:
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_auth"
    assert not result["errors"]

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            side_effect=MyPVAuthenticationError(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "wrong-password"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_auth"
    assert result["errors"]["password"] == "invalid_password"


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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_auth"
    assert not result["errors"]

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.serial_number",
            "1601500000000000",
        ),
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.model",
            "AC ELWA 2",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "test-password"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "my-PV AC ELWA 2"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == "1601500000000000"


async def test_step_zeroconf_wrong_password(hass: HomeAssistant) -> None:
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_auth"
    assert not result["errors"]

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            side_effect=MyPVAuthenticationError(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "wrong-password"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_auth"
    assert result["errors"]["password"] == "invalid_password"
