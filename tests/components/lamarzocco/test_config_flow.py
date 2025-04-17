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
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import USER_INPUT, async_init_integration, get_bluetooth_service_info

from tests.common import MockConfigEntry


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

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_MACHINE: "GS012345"},
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY

    assert result3["title"] == "GS012345"
    assert result3["data"] == {
        **USER_INPUT,
        CONF_TOKEN: None,
    }
    assert result3["result"].unique_id == "GS012345"


async def test_form(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    mock_setup_entry: Generator[AsyncMock],
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result2 = await __do_successful_user_step(hass, result, mock_cloud_client)
    await __do_sucessful_machine_selection_step(hass, result2)


async def test_form_abort_already_configured(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "machine_selection"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_MACHINE: "GS012345",
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "already_configured"


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
    mock_setup_entry: Generator[AsyncMock],
    side_effect: Exception,
    error: str,
) -> None:
    """Test invalid auth error."""

    mock_cloud_client.list_things.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}
    assert len(mock_cloud_client.list_things.mock_calls) == 1

    # test recovery from failure
    mock_cloud_client.list_things.side_effect = None
    result2 = await __do_successful_user_step(hass, result, mock_cloud_client)
    await __do_sucessful_machine_selection_step(hass, result2)


async def test_form_no_machines(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    mock_setup_entry: Generator[AsyncMock],
) -> None:
    """Test we don't have any devices."""

    original_return = mock_cloud_client.list_things.return_value
    mock_cloud_client.list_things.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "no_machines"}
    assert len(mock_cloud_client.list_things.mock_calls) == 1

    # test recovery from failure
    mock_cloud_client.list_things.return_value = original_return

    result2 = await __do_successful_user_step(hass, result, mock_cloud_client)
    await __do_sucessful_machine_selection_step(hass, result2)


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

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new_password"},
    )

    assert result2["type"] is FlowResultType.ABORT
    await hass.async_block_till_done()
    assert result2["reason"] == "reauth_successful"
    assert len(mock_cloud_client.list_things.mock_calls) == 1
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: Generator[AsyncMock],
) -> None:
    """Testing reconfgure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result2 = await __do_successful_user_step(hass, result, mock_cloud_client)
    service_info = get_bluetooth_service_info(ModelName.GS3_MP, "GS012345")

    with (
        patch(
            "homeassistant.components.lamarzocco.config_flow.async_discovered_service_info",
            return_value=[service_info],
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_MACHINE: "GS012345",
            },
        )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "bluetooth_selection"

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {CONF_MAC: service_info.address},
    )

    assert result4["type"] is FlowResultType.ABORT
    assert result4["reason"] == "reconfigure_successful"

    assert mock_config_entry.title == "My LaMarzocco"
    assert mock_config_entry.data == {
        **mock_config_entry.data,
        CONF_MAC: service_info.address,
    }


async def test_bluetooth_discovery(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_cloud_client: MagicMock,
    mock_setup_entry: Generator[AsyncMock],
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

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY

    assert result2["title"] == "GS012345"
    assert result2["data"] == {
        **USER_INPUT,
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
        CONF_TOKEN: "dummyToken",
    }


async def test_bluetooth_discovery_already_configured(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_cloud_client: MagicMock,
    mock_setup_entry: Generator[AsyncMock],
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
    mock_setup_entry: Generator[AsyncMock],
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

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "machine_not_found"}
    assert len(mock_cloud_client.list_things.mock_calls) == 1

    mock_cloud_client.list_things.return_value = original_return
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY

    assert result2["title"] == "GS012345"
    assert result2["data"] == {
        **USER_INPUT,
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
        CONF_TOKEN: None,
    }


async def test_dhcp_discovery(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_cloud_client: MagicMock,
    mock_setup_entry: Generator[AsyncMock],
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

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        **USER_INPUT,
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_TOKEN: None,
    }


async def test_dhcp_discovery_abort_on_hostname_changed(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_cloud_client: MagicMock,
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
    mock_cloud_client: MagicMock,
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
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: Generator[AsyncMock],
) -> None:
    """Test options flow."""
    await async_init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_USE_BLUETOOTH: False,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_USE_BLUETOOTH: False,
    }
