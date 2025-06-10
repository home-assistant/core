"""Test the La Marzocco config flow."""

from collections.abc import Generator
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

from pylamarzocco.const import ModelName
from pylamarzocco.exceptions import AuthFail, RequestNotSuccessful
import pytest

from homeassistant.components.lamarzocco.config_flow import CONF_MACHINE
from homeassistant.components.lamarzocco.const import CONF_USE_BLUETOOTH, DOMAIN
from homeassistant.config_entries import (
    SOURCE_BLUETOOTH,
    SOURCE_DHCP,
    SOURCE_USER,
    ConfigEntryState,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ADDRESS, CONF_MAC, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import USER_INPUT, async_init_integration, get_bluetooth_service_info

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.lamarzocco.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def __do_successful_user_step(
    hass: HomeAssistant, result: ConfigFlowResult, mock_cloud_client: MagicMock
) -> ConfigFlowResult:
    """Successfully configure the user step."""
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "machine_selection"
    return result2


async def __do_sucessful_machine_selection_step(
    hass: HomeAssistant, result2: ConfigFlowResult
) -> None:
    """Successfully configure the machine selection step."""

    result = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_MACHINE: "GS012345"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert result["title"] == "GS012345"
    assert result["data"] == {
        **USER_INPUT,
        CONF_TOKEN: None,
    }
    assert result["result"].unique_id == "GS012345"


async def test_form(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await __do_successful_user_step(hass, result, mock_cloud_client)
    await __do_sucessful_machine_selection_step(hass, result)


async def test_form_abort_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "machine_selection"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_MACHINE: "GS012345",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (AuthFail(""), "invalid_auth"),
        (RequestNotSuccessful(""), "cannot_connect"),
    ],
)
async def test_form_invalid_auth(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test invalid auth error."""

    mock_cloud_client.list_things.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert len(mock_cloud_client.list_things.mock_calls) == 1

    # test recovery from failure
    mock_cloud_client.list_things.side_effect = None
    result = await __do_successful_user_step(hass, result, mock_cloud_client)
    await __do_sucessful_machine_selection_step(hass, result)


async def test_form_no_machines(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
) -> None:
    """Test we don't have any devices."""

    original_return = mock_cloud_client.list_things.return_value
    mock_cloud_client.list_things.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_machines"}
    assert len(mock_cloud_client.list_things.mock_calls) == 1

    # test recovery from failure
    mock_cloud_client.list_things.return_value = original_return

    result = await __do_successful_user_step(hass, result, mock_cloud_client)
    await __do_sucessful_machine_selection_step(hass, result)


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the reauth flow."""

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new_password"},
    )

    assert result["type"] is FlowResultType.ABORT
    await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert len(mock_cloud_client.list_things.mock_calls) == 1
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Testing reconfgure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await __do_successful_user_step(hass, result, mock_cloud_client)
    service_info = get_bluetooth_service_info(ModelName.GS3_MP, "GS012345")

    with (
        patch(
            "homeassistant.components.lamarzocco.config_flow.async_discovered_service_info",
            return_value=[service_info],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_MACHINE: "GS012345",
            },
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_selection"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MAC: service_info.address},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert mock_config_entry.title == "My LaMarzocco"
    assert mock_config_entry.data == {
        **mock_config_entry.data,
        CONF_MAC: service_info.address,
    }


@pytest.mark.parametrize(
    "discovered",
    [
        [],
        [
            BluetoothServiceInfo(
                name="SomeDevice",
                address="aa:bb:cc:dd:ee:ff",
                rssi=-63,
                manufacturer_data={},
                service_data={},
                service_uuids=[],
                source="local",
            )
        ],
    ],
)
async def test_reconfigure_flow_no_machines(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    discovered: list[BluetoothServiceInfo],
) -> None:
    """Testing reconfgure flow."""
    mock_config_entry.add_to_hass(hass)

    data = deepcopy(dict(mock_config_entry.data))
    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await __do_successful_user_step(hass, result, mock_cloud_client)

    with (
        patch(
            "homeassistant.components.lamarzocco.config_flow.async_discovered_service_info",
            return_value=discovered,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_MACHINE: "GS012345",
            },
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert mock_config_entry.title == "My LaMarzocco"
    assert CONF_MAC not in mock_config_entry.data
    assert dict(mock_config_entry.data) == data


async def test_bluetooth_discovery(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_cloud_client: MagicMock,
) -> None:
    """Test bluetooth discovery."""
    service_info = get_bluetooth_service_info(
        ModelName.GS3_MP, mock_lamarzocco.serial_number
    )
    mock_cloud_client.list_things.return_value[0].ble_auth_token = "dummyToken"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert result["title"] == "GS012345"
    assert result["data"] == {
        **USER_INPUT,
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
        CONF_TOKEN: "dummyToken",
    }


async def test_bluetooth_discovery_already_configured(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test bluetooth discovery."""
    mock_config_entry.add_to_hass(hass)

    service_info = get_bluetooth_service_info(
        ModelName.GS3_MP, mock_lamarzocco.serial_number
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_errors(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_cloud_client: MagicMock,
) -> None:
    """Test bluetooth discovery errors."""
    service_info = get_bluetooth_service_info(
        ModelName.GS3_MP, mock_lamarzocco.serial_number
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=service_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    original_return = deepcopy(mock_cloud_client.list_things.return_value)
    mock_cloud_client.list_things.return_value[0].serial_number = "GS98765"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "machine_not_found"}
    assert len(mock_cloud_client.list_things.mock_calls) == 1

    mock_cloud_client.list_things.return_value = original_return
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert result["title"] == "GS012345"
    assert result["data"] == {
        **USER_INPUT,
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
        CONF_TOKEN: None,
    }


async def test_dhcp_discovery(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test dhcp discovery."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.42",
            hostname=mock_lamarzocco.serial_number,
            macaddress="aa:bb:cc:dd:ee:ff",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        **USER_INPUT,
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_TOKEN: None,
    }


async def test_dhcp_discovery_abort_on_hostname_changed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test dhcp discovery aborts when hostname was changed manually."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.42",
            hostname="custom_name",
            macaddress="00:00:00:00:00:00",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_already_configured_and_update(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test discovered IP address change."""
    old_address = mock_config_entry.data[CONF_ADDRESS]

    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.42",
            hostname=mock_lamarzocco.serial_number,
            macaddress="aa:bb:cc:dd:ee:ff",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_config_entry.data[CONF_ADDRESS] != old_address
    assert mock_config_entry.data[CONF_ADDRESS] == "aa:bb:cc:dd:ee:ff"


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow."""
    await async_init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_USE_BLUETOOTH: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_USE_BLUETOOTH: False,
    }
