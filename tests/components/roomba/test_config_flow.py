"""Test the iRobot Roomba config flow."""

from ipaddress import ip_address
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from roombapy import RoombaConnectionError, RoombaInfo

from homeassistant.components import dhcp, zeroconf
from homeassistant.components.roomba import config_flow
from homeassistant.components.roomba.const import CONF_BLID, CONF_CONTINUOUS, DOMAIN
from homeassistant.config_entries import (
    SOURCE_DHCP,
    SOURCE_IGNORE,
    SOURCE_USER,
    SOURCE_ZEROCONF,
)
from homeassistant.const import CONF_DELAY, CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_IP = "1.2.3.4"
VALID_CONFIG = {CONF_HOST: MOCK_IP, CONF_BLID: "BLID", CONF_PASSWORD: "password"}

DISCOVERY_DEVICES = [
    (
        SOURCE_DHCP,
        dhcp.DhcpServiceInfo(
            ip=MOCK_IP,
            macaddress="501479ddeeff",
            hostname="irobot-blid",
        ),
    ),
    (
        SOURCE_DHCP,
        dhcp.DhcpServiceInfo(
            ip=MOCK_IP,
            macaddress="80a589ddeeff",
            hostname="roomba-blid",
        ),
    ),
    (
        SOURCE_ZEROCONF,
        zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address(MOCK_IP),
            ip_addresses=[ip_address(MOCK_IP)],
            hostname="irobot-blid.local.",
            name="irobot-blid._amzn-alexa._tcp.local.",
            type="_amzn-alexa._tcp.local.",
            port=443,
            properties={},
        ),
    ),
    (
        SOURCE_ZEROCONF,
        zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address(MOCK_IP),
            ip_addresses=[ip_address(MOCK_IP)],
            hostname="roomba-blid.local.",
            name="roomba-blid._amzn-alexa._tcp.local.",
            type="_amzn-alexa._tcp.local.",
            port=443,
            properties={},
        ),
    ),
]


DHCP_DISCOVERY_DEVICES_WITHOUT_MATCHING_IP = [
    dhcp.DhcpServiceInfo(
        ip="4.4.4.4",
        macaddress="50:14:79:DD:EE:FF",
        hostname="irobot-blid",
    ),
    dhcp.DhcpServiceInfo(
        ip="5.5.5.5",
        macaddress="80:A5:89:DD:EE:FF",
        hostname="roomba-blid",
    ),
]


@pytest.fixture(autouse=True)
def roomba_no_wake_time():
    """Fixture that prevents sleep."""
    with patch.object(config_flow, "ROOMBA_WAKE_TIME", 0):
        yield


def _create_mocked_roomba(
    roomba_connected=None, master_state=None, connect=None, disconnect=None
):
    mocked_roomba = MagicMock()
    type(mocked_roomba).roomba_connected = PropertyMock(return_value=roomba_connected)
    type(mocked_roomba).master_state = PropertyMock(return_value=master_state)
    type(mocked_roomba).connect = MagicMock(side_effect=connect)
    type(mocked_roomba).disconnect = MagicMock(side_effect=disconnect)
    return mocked_roomba


def _mocked_discovery(*_):
    roomba_discovery = MagicMock()

    roomba = RoombaInfo(
        hostname="irobot-BLID",
        robot_name="robot_name",
        ip=MOCK_IP,
        mac="mac",
        firmware="firmware",
        sku="sku",
        capabilities={"cap": 1},
    )

    roomba_discovery.get_all = MagicMock(return_value=[roomba])
    roomba_discovery.get = MagicMock(return_value=roomba)

    return roomba_discovery


def _mocked_no_devices_found_discovery(*_):
    roomba_discovery = MagicMock()
    roomba_discovery.get_all = MagicMock(return_value=[])
    roomba_discovery.get = MagicMock(return_value=None)
    return roomba_discovery


def _mocked_failed_discovery(*_):
    roomba_discovery = MagicMock()
    roomba_discovery.get_all = MagicMock(side_effect=OSError)
    roomba_discovery.get = MagicMock(side_effect=OSError)
    return roomba_discovery


def _mocked_getpassword(*_):
    roomba_password = MagicMock()
    roomba_password.get_password = MagicMock(return_value="password")
    return roomba_password


def _mocked_failed_getpassword(*_):
    roomba_password = MagicMock()
    roomba_password.get_password = MagicMock(return_value=None)
    return roomba_password


def _mocked_connection_refused_on_getpassword(*_):
    roomba_password = MagicMock()
    roomba_password.get_password = MagicMock(side_effect=ConnectionRefusedError)
    return roomba_password


async def test_form_user_discovery_and_password_fetch(hass: HomeAssistant) -> None:
    """Test we can discovery and fetch the password."""

    mocked_roomba = _create_mocked_roomba(
        roomba_connected=True,
        master_state={"state": {"reported": {"name": "myroomba"}}},
    )

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_IP},
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] is None
    assert result2["step_id"] == "link"

    with (
        patch(
            "homeassistant.components.roomba.config_flow.RoombaFactory.create_roomba",
            return_value=mocked_roomba,
        ),
        patch(
            "homeassistant.components.roomba.config_flow.RoombaPassword",
            _mocked_getpassword,
        ),
        patch(
            "homeassistant.components.roomba.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "robot_name"
    assert result3["result"].unique_id == "BLID"
    assert result3["data"] == {
        CONF_BLID: "BLID",
        CONF_CONTINUOUS: True,
        CONF_DELAY: 1,
        CONF_HOST: MOCK_IP,
        CONF_PASSWORD: "password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_discovery_skips_known(hass: HomeAssistant) -> None:
    """Test discovery proceeds to manual if all discovered are already known."""

    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG, unique_id="BLID")
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "manual"


async def test_form_user_no_devices_found_discovery_aborts_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test if we manually configure an existing host we abort."""

    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG, unique_id="BLID")
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery",
        _mocked_no_devices_found_discovery,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "manual"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_IP},
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_user_discovery_manual_and_auto_password_fetch(
    hass: HomeAssistant,
) -> None:
    """Test discovery skipped and we can auto fetch the password."""

    mocked_roomba = _create_mocked_roomba(
        roomba_connected=True,
        master_state={"state": {"reported": {"name": "myroomba"}}},
    )

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: None},
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] is None
    assert result2["step_id"] == "manual"

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_HOST: MOCK_IP},
        )

    await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] is None

    with (
        patch(
            "homeassistant.components.roomba.config_flow.RoombaFactory.create_roomba",
            return_value=mocked_roomba,
        ),
        patch(
            "homeassistant.components.roomba.config_flow.RoombaPassword",
            _mocked_getpassword,
        ),
        patch(
            "homeassistant.components.roomba.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == "robot_name"
    assert result4["result"].unique_id == "BLID"
    assert result4["data"] == {
        CONF_BLID: "BLID",
        CONF_CONTINUOUS: True,
        CONF_DELAY: 1,
        CONF_HOST: MOCK_IP,
        CONF_PASSWORD: "password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_discover_fails_aborts_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test if we manually configure an existing host we abort after failed discovery."""

    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG, unique_id="BLID")
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery",
        _mocked_failed_discovery,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "manual"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_IP},
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_user_discovery_manual_and_auto_password_fetch_but_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test discovery skipped and we can auto fetch the password then we fail to connect."""

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: None},
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] is None
    assert result2["step_id"] == "manual"

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery",
        _mocked_no_devices_found_discovery,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_HOST: MOCK_IP},
        )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "cannot_connect"


async def test_form_user_discovery_no_devices_found_and_auto_password_fetch(
    hass: HomeAssistant,
) -> None:
    """Test discovery finds no devices and we can auto fetch the password."""

    mocked_roomba = _create_mocked_roomba(
        roomba_connected=True,
        master_state={"state": {"reported": {"name": "myroomba"}}},
    )

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery",
        _mocked_no_devices_found_discovery,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "manual"

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_IP},
        )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] is None

    with (
        patch(
            "homeassistant.components.roomba.config_flow.RoombaFactory.create_roomba",
            return_value=mocked_roomba,
        ),
        patch(
            "homeassistant.components.roomba.config_flow.RoombaPassword",
            _mocked_getpassword,
        ),
        patch(
            "homeassistant.components.roomba.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "robot_name"
    assert result3["result"].unique_id == "BLID"
    assert result3["data"] == {
        CONF_BLID: "BLID",
        CONF_CONTINUOUS: True,
        CONF_DELAY: 1,
        CONF_HOST: MOCK_IP,
        CONF_PASSWORD: "password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_discovery_no_devices_found_and_password_fetch_fails(
    hass: HomeAssistant,
) -> None:
    """Test discovery finds no devices and password fetch fails."""

    mocked_roomba = _create_mocked_roomba(
        roomba_connected=True,
        master_state={"state": {"reported": {"name": "myroomba"}}},
    )

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery",
        _mocked_no_devices_found_discovery,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "manual"

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_IP},
        )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] is None

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaPassword",
        _mocked_failed_getpassword,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.roomba.config_flow.RoombaFactory.create_roomba",
            return_value=mocked_roomba,
        ),
        patch(
            "homeassistant.components.roomba.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == "myroomba"
    assert result4["result"].unique_id == "BLID"
    assert result4["data"] == {
        CONF_BLID: "BLID",
        CONF_CONTINUOUS: True,
        CONF_DELAY: 1,
        CONF_HOST: MOCK_IP,
        CONF_PASSWORD: "password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_discovery_not_devices_found_and_password_fetch_fails_and_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test discovery finds no devices and password fetch fails then we cannot connect."""

    mocked_roomba = _create_mocked_roomba(
        connect=RoombaConnectionError,
        roomba_connected=True,
        master_state={"state": {"reported": {"name": "myroomba"}}},
    )

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery",
        _mocked_no_devices_found_discovery,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "manual"

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_IP},
        )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] is None

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaPassword",
        _mocked_failed_getpassword,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.roomba.config_flow.RoombaFactory.create_roomba",
            return_value=mocked_roomba,
        ),
        patch(
            "homeassistant.components.roomba.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

    assert result4["type"] is FlowResultType.FORM
    assert result4["errors"] == {"base": "cannot_connect"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_user_discovery_and_password_fetch_gets_connection_refused(
    hass: HomeAssistant,
) -> None:
    """Test we can discovery and fetch the password manually."""

    mocked_roomba = _create_mocked_roomba(
        roomba_connected=True,
        master_state={"state": {"reported": {"name": "myroomba"}}},
    )

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_IP},
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] is None
    assert result2["step_id"] == "link"

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaPassword",
        _mocked_connection_refused_on_getpassword,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.roomba.config_flow.RoombaFactory.create_roomba",
            return_value=mocked_roomba,
        ),
        patch(
            "homeassistant.components.roomba.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == "myroomba"
    assert result4["result"].unique_id == "BLID"
    assert result4["data"] == {
        CONF_BLID: "BLID",
        CONF_CONTINUOUS: True,
        CONF_DELAY: 1,
        CONF_HOST: MOCK_IP,
        CONF_PASSWORD: "password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("discovery_data", DISCOVERY_DEVICES)
async def test_dhcp_discovery_and_roomba_discovery_finds(
    hass: HomeAssistant,
    discovery_data: tuple[str, dhcp.DhcpServiceInfo | zeroconf.ZeroconfServiceInfo],
) -> None:
    """Test we can process the discovery from dhcp and roomba discovery matches the device."""

    mocked_roomba = _create_mocked_roomba(
        roomba_connected=True,
        master_state={"state": {"reported": {"name": "myroomba"}}},
    )
    source, discovery = discovery_data

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=discovery,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "link"
    assert result["description_placeholders"] == {"name": "robot_name"}

    with (
        patch(
            "homeassistant.components.roomba.config_flow.RoombaFactory.create_roomba",
            return_value=mocked_roomba,
        ),
        patch(
            "homeassistant.components.roomba.config_flow.RoombaPassword",
            _mocked_getpassword,
        ),
        patch(
            "homeassistant.components.roomba.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "robot_name"
    assert result2["result"].unique_id == "BLID"
    assert result2["data"] == {
        CONF_BLID: "BLID",
        CONF_CONTINUOUS: True,
        CONF_DELAY: 1,
        CONF_HOST: MOCK_IP,
        CONF_PASSWORD: "password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("discovery_data", DHCP_DISCOVERY_DEVICES_WITHOUT_MATCHING_IP)
async def test_dhcp_discovery_falls_back_to_manual(
    hass: HomeAssistant, discovery_data
) -> None:
    """Test we can process the discovery from dhcp but roomba discovery cannot find the specific device."""

    mocked_roomba = _create_mocked_roomba(
        roomba_connected=True,
        master_state={"state": {"reported": {"name": "myroomba"}}},
    )

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=discovery_data,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] is None
    assert result2["step_id"] == "manual"

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_HOST: MOCK_IP},
        )
    await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] is None

    with (
        patch(
            "homeassistant.components.roomba.config_flow.RoombaFactory.create_roomba",
            return_value=mocked_roomba,
        ),
        patch(
            "homeassistant.components.roomba.config_flow.RoombaPassword",
            _mocked_getpassword,
        ),
        patch(
            "homeassistant.components.roomba.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == "robot_name"
    assert result4["result"].unique_id == "BLID"
    assert result4["data"] == {
        CONF_BLID: "BLID",
        CONF_CONTINUOUS: True,
        CONF_DELAY: 1,
        CONF_HOST: MOCK_IP,
        CONF_PASSWORD: "password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("discovery_data", DHCP_DISCOVERY_DEVICES_WITHOUT_MATCHING_IP)
async def test_dhcp_discovery_no_devices_falls_back_to_manual(
    hass: HomeAssistant, discovery_data
) -> None:
    """Test we can process the discovery from dhcp but roomba discovery cannot find any devices."""

    mocked_roomba = _create_mocked_roomba(
        roomba_connected=True,
        master_state={"state": {"reported": {"name": "myroomba"}}},
    )

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery",
        _mocked_no_devices_found_discovery,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=discovery_data,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "manual"

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_IP},
        )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] is None

    with (
        patch(
            "homeassistant.components.roomba.config_flow.RoombaFactory.create_roomba",
            return_value=mocked_roomba,
        ),
        patch(
            "homeassistant.components.roomba.config_flow.RoombaPassword",
            _mocked_getpassword,
        ),
        patch(
            "homeassistant.components.roomba.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "robot_name"
    assert result3["result"].unique_id == "BLID"
    assert result3["data"] == {
        CONF_BLID: "BLID",
        CONF_CONTINUOUS: True,
        CONF_DELAY: 1,
        CONF_HOST: MOCK_IP,
        CONF_PASSWORD: "password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_with_ignored(hass: HomeAssistant) -> None:
    """Test ignored entries do not break checking for existing entries."""

    config_entry = MockConfigEntry(domain=DOMAIN, data={}, source=SOURCE_IGNORE)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip=MOCK_IP,
                macaddress="aabbccddeeff",
                hostname="irobot-blid",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM


async def test_dhcp_discovery_already_configured_host(hass: HomeAssistant) -> None:
    """Test we abort if the host is already configured."""

    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: MOCK_IP})
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip=MOCK_IP,
                macaddress="aabbccddeeff",
                hostname="irobot-blid",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery_already_configured_blid(hass: HomeAssistant) -> None:
    """Test we abort if the blid is already configured."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BLID: "BLID"}, unique_id="BLID"
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip=MOCK_IP,
                macaddress="aabbccddeeff",
                hostname="irobot-blid",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery_not_irobot(hass: HomeAssistant) -> None:
    """Test we abort if the discovered device is not an irobot device."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BLID: "BLID"}, unique_id="BLID"
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip=MOCK_IP,
                macaddress="aabbccddeeff",
                hostname="Notirobot-blid",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_irobot_device"


async def test_dhcp_discovery_partial_hostname(hass: HomeAssistant) -> None:
    """Test we abort flows when we have a partial hostname."""

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip=MOCK_IP,
                macaddress="aabbccddeeff",
                hostname="irobot-blid",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip=MOCK_IP,
                macaddress="aabbccddeeff",
                hostname="irobot-blidthatislonger",
            ),
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "link"

    current_flows = hass.config_entries.flow.async_progress()
    assert len(current_flows) == 1
    assert current_flows[0]["flow_id"] == result2["flow_id"]

    with patch(
        "homeassistant.components.roomba.config_flow.RoombaDiscovery", _mocked_discovery
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip=MOCK_IP,
                macaddress="aabbccddeeff",
                hostname="irobot-bl",
            ),
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "short_blid"

    current_flows = hass.config_entries.flow.async_progress()
    assert len(current_flows) == 1
    assert current_flows[0]["flow_id"] == result2["flow_id"]


async def test_options_flow(
    hass: HomeAssistant,
) -> None:
    """Test config flow options."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
        unique_id="BLID",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.roomba.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_CONTINUOUS: True, CONF_DELAY: 1},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_CONTINUOUS: True, CONF_DELAY: 1}
    assert config_entry.options == {CONF_CONTINUOUS: True, CONF_DELAY: 1}
