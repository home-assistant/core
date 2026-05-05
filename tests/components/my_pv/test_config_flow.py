"""Test the my-PV config flow."""

from ipaddress import ip_address
from unittest.mock import patch

from my_pv.exceptions import MyPVAuthenticationError

from homeassistant import config_entries
from homeassistant.components.my_pv.const import (
    CONF_SERIAL_NUMBER,
    CONF_TYPE_CLOUD,
    CONF_TYPE_LOCAL,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

MOCK_CONFIG_LOCAL_AUTH = {
    CONF_PASSWORD: "test-password",
}

MOCK_CONFIG_CLOUD = {
    CONF_TYPE: CONF_TYPE_CLOUD,
    CONF_SERIAL_NUMBER: "1601500000000000",
    CONF_TOKEN: "my0000000000000000000000000000000000000000000000PV",
}

MOCK_CONFIG_CLOUD_REAUTH = {
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


async def test_step_setup_local(hass: HomeAssistant) -> None:
    """Test if we get the local setup form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert "setup_local" in result["menu_options"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "setup_local"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_local"
    assert result["errors"] is None

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
        CONF_TYPE: CONF_TYPE_LOCAL,
        CONF_HOST: "127.0.0.1",
    }
    assert result["result"].unique_id == "1601500000000000"


async def test_step_local_auth(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert "setup_local" in result["menu_options"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "setup_local"}
    )

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
            result["flow_id"],
            {
                CONF_HOST: "127.0.0.1",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_auth"

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
        CONF_TYPE: CONF_TYPE_LOCAL,
        CONF_HOST: "127.0.0.1",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == "1601500000000000"


async def test_step_setup_cloud(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert "setup_cloud" in result["menu_options"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "setup_cloud"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_cloud"
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.my_pv.MyPVCloudDevice.connect",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL_NUMBER: "1601500000000000",
                CONF_TOKEN: "my0000000000000000000000000000000000000000000000PV",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "my-PV AC ELWA 2"
    assert result["data"] == {
        CONF_TYPE: CONF_TYPE_CLOUD,
        CONF_SERIAL_NUMBER: "1601500000000000",
        CONF_TOKEN: "my0000000000000000000000000000000000000000000000PV",
    }
    assert result["result"].unique_id == "1601500000000000"


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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

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
        result = await hass.config_entries.flow.async_configure(result["flow_id"], [])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "my-PV AC ELWA 2"
    assert result["data"] == {
        CONF_TYPE: CONF_TYPE_LOCAL,
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
    assert result["step_id"] == "local_auth"

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
        CONF_TYPE: CONF_TYPE_LOCAL,
        CONF_HOST: "127.0.0.1",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == "1601500000000000"


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
    assert result["step_id"] == "local_auth"

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
        CONF_TYPE: CONF_TYPE_LOCAL,
        CONF_HOST: "127.0.0.1",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == "1601500000000000"


async def test_step_local_reauth(
    hass: HomeAssistant,
    mock_local_config_entry: MockConfigEntry,
) -> None:
    """Test for reauth of local devices."""
    mock_local_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            side_effect=MyPVAuthenticationError(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_local_config_entry.entry_id,
            },
            data=mock_local_config_entry.data,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_auth"

    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice.connect",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "new-password",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    updated_entry = hass.config_entries.async_get_entry(
        mock_local_config_entry.entry_id
    )
    assert updated_entry.data[CONF_PASSWORD] == "new-password"


async def test_step_cloud_reauth(
    hass: HomeAssistant,
    mock_cloud_config_entry: MockConfigEntry,
) -> None:
    """Test for reauth of local devices."""
    mock_cloud_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.my_pv.MyPVCloudDevice.connect",
            side_effect=MyPVAuthenticationError(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_cloud_config_entry.entry_id,
            },
            data=mock_cloud_config_entry.data,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_cloud"

    with (
        patch(
            "homeassistant.components.my_pv.MyPVCloudDevice.connect",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_TOKEN: "my0000000000000000000000000000000000000000000001PV",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    updated_entry = hass.config_entries.async_get_entry(
        mock_cloud_config_entry.entry_id
    )
    assert (
        updated_entry.data[CONF_TOKEN]
        == "my0000000000000000000000000000000000000000000001PV"
    )
