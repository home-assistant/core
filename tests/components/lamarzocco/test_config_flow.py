"""Test the La Marzocco config flow."""

from collections.abc import Generator
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

from pylamarzocco.const import DeviceType, ModelName
from pylamarzocco.exceptions import (
    AuthFail,
    PolicyAcceptanceRequired,
    RequestNotSuccessful,
)
from pylamarzocco.models import Thing
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_json_object_fixture

from homeassistant.components.lamarzocco.config_flow import (
    CONF_COMMERCIAL_POLICY,
    CONF_MACHINE,
    CONF_PROFILE_POLICY,
)
from homeassistant.components.lamarzocco.const import (
    CONF_INSTALLATION_KEY,
    CONF_OFFLINE_MODE,
    CONF_USE_BLUETOOTH,
    DOMAIN,
)
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

from . import (
    MOCK_INSTALLATION_KEY,
    USER_INPUT,
    async_init_integration,
    get_bluetooth_service_info,
)


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.lamarzocco.async_setup_entry", return_value=None
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
        CONF_INSTALLATION_KEY: MOCK_INSTALLATION_KEY,
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
        (TimeoutError(), "cannot_connect"),
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


async def test_form_accept_policy(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the privacy policy is accepted when the cloud requires it."""
    mock_cloud_client.list_things.side_effect = [
        PolicyAcceptanceRequired(""),
        mock_cloud_client.list_things.return_value,
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "accept_policy"
    mock_cloud_client.accept_privacy_policy.assert_not_called()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE_POLICY: True, CONF_COMMERCIAL_POLICY: False},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "machine_selection"
    mock_cloud_client.accept_privacy_policy.assert_awaited_once_with(
        profile_policy=True, commercial_policy=False
    )
    await __do_sucessful_machine_selection_step(hass, result)


@pytest.mark.parametrize(
    ("accept_errors", "list_things_errors", "error"),
    [
        pytest.param(
            [RequestNotSuccessful("")], [], "cannot_connect", id="accept_failed"
        ),
        pytest.param([TimeoutError()], [], "cannot_connect", id="accept_timeout"),
        pytest.param(
            [], [RequestNotSuccessful("")], "cannot_connect", id="list_things_failed"
        ),
        pytest.param([], [TimeoutError()], "cannot_connect", id="list_things_timeout"),
        pytest.param(
            [],
            [PolicyAcceptanceRequired("")],
            "policy_not_accepted",
            id="policy_not_accepted",
        ),
    ],
)
async def test_form_accept_policy_errors(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    accept_errors: list[Exception],
    list_things_errors: list[Exception],
    error: str,
) -> None:
    """Test recoverable errors while accepting the privacy policy."""
    mock_cloud_client.list_things.side_effect = [
        PolicyAcceptanceRequired(""),
        *list_things_errors,
        mock_cloud_client.list_things.return_value,
    ]
    mock_cloud_client.accept_privacy_policy.side_effect = [*accept_errors, None]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE_POLICY: False, CONF_COMMERCIAL_POLICY: False},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "accept_policy"
    assert result["errors"] == {"base": error}

    # test recovery from failure
    mock_cloud_client.accept_privacy_policy.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE_POLICY: False, CONF_COMMERCIAL_POLICY: False},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "machine_selection"
    await __do_sucessful_machine_selection_step(hass, result)


async def test_form_accept_policy_invalid_auth(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
) -> None:
    """Test an auth error while accepting the policy returns to the user step."""
    mock_cloud_client.list_things.side_effect = [
        PolicyAcceptanceRequired(""),
        PolicyAcceptanceRequired(""),
        mock_cloud_client.list_things.return_value,
    ]
    mock_cloud_client.accept_privacy_policy.side_effect = [AuthFail(""), None]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE_POLICY: False, CONF_COMMERCIAL_POLICY: False},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    # test recovery by submitting the credentials again
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "accept_policy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE_POLICY: False, CONF_COMMERCIAL_POLICY: False},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "machine_selection"
    assert len(mock_cloud_client.accept_privacy_policy.mock_calls) == 2
    await __do_sucessful_machine_selection_step(hass, result)


async def test_form_accept_policy_no_machines(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
) -> None:
    """Test we abort when the account has no machines after accepting the policy."""
    mock_cloud_client.list_things.side_effect = [PolicyAcceptanceRequired(""), []]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE_POLICY: False, CONF_COMMERCIAL_POLICY: False},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_machines"


async def test_grinders_not_configurable(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
) -> None:
    """Test that grinders are filtered out so only machines can be configured."""
    grinder = await async_load_json_object_fixture(hass, "thing.json", DOMAIN)
    grinder["type"] = DeviceType.GRINDER
    grinder["serialNumber"] = "GR012345"
    grinder["name"] = "GR012345"

    mock_cloud_client.list_things.return_value = [
        *mock_cloud_client.list_things.return_value,
        Thing.from_dict(grinder),
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await __do_successful_user_step(hass, result, mock_cloud_client)

    options = result["data_schema"].schema[CONF_MACHINE].config["options"]
    assert [option["value"] for option in options] == ["GS012345"]


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


async def test_reauth_flow_accept_policy(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the privacy policy is accepted during reauth."""
    mock_config_entry.add_to_hass(hass)
    mock_cloud_client.list_things.side_effect = [
        PolicyAcceptanceRequired(""),
        mock_cloud_client.list_things.return_value,
    ]

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new_password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "accept_policy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE_POLICY: False, CONF_COMMERCIAL_POLICY: True},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    mock_cloud_client.accept_privacy_policy.assert_awaited_once_with(
        profile_policy=False, commercial_policy=True
    )
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"


@pytest.mark.parametrize(
    ("accept_errors", "list_things_errors", "error"),
    [
        pytest.param(
            [RequestNotSuccessful("")], [], "cannot_connect", id="accept_failed"
        ),
        pytest.param([TimeoutError()], [], "cannot_connect", id="accept_timeout"),
        pytest.param(
            [], [RequestNotSuccessful("")], "cannot_connect", id="list_things_failed"
        ),
        pytest.param([], [TimeoutError()], "cannot_connect", id="list_things_timeout"),
        pytest.param(
            [],
            [PolicyAcceptanceRequired("")],
            "policy_not_accepted",
            id="policy_not_accepted",
        ),
    ],
)
async def test_reauth_flow_accept_policy_errors(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    accept_errors: list[Exception],
    list_things_errors: list[Exception],
    error: str,
) -> None:
    """Test recoverable errors while accepting the privacy policy during reauth."""
    mock_config_entry.add_to_hass(hass)
    mock_cloud_client.list_things.side_effect = [
        PolicyAcceptanceRequired(""),
        *list_things_errors,
        mock_cloud_client.list_things.return_value,
    ]
    mock_cloud_client.accept_privacy_policy.side_effect = [*accept_errors, None]

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new_password"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE_POLICY: False, CONF_COMMERCIAL_POLICY: False},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "accept_policy"
    assert result["errors"] == {"base": error}

    # test recovery from failure
    mock_cloud_client.accept_privacy_policy.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE_POLICY: False, CONF_COMMERCIAL_POLICY: False},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"


async def test_reauth_flow_accept_policy_invalid_auth(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an auth error while accepting the policy returns to reauth confirm."""
    mock_config_entry.add_to_hass(hass)
    mock_cloud_client.list_things.side_effect = [
        PolicyAcceptanceRequired(""),
        PolicyAcceptanceRequired(""),
        mock_cloud_client.list_things.return_value,
    ]
    mock_cloud_client.accept_privacy_policy.side_effect = [AuthFail(""), None]

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new_password"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE_POLICY: False, CONF_COMMERCIAL_POLICY: False},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    # test recovery by submitting corrected credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "corrected_password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "accept_policy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE_POLICY: False, CONF_COMMERCIAL_POLICY: False},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "corrected_password"


async def test_reauth_flow_accept_policy_no_machines(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth aborts when the account has no machines after accepting the policy."""
    mock_config_entry.add_to_hass(hass)
    mock_cloud_client.list_things.side_effect = [PolicyAcceptanceRequired(""), []]

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new_password"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE_POLICY: False, CONF_COMMERCIAL_POLICY: False},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_machines"
    assert mock_config_entry.data[CONF_PASSWORD] != "new_password"


@pytest.mark.parametrize(
    "ble_name",
    [
        pytest.param("GS3_GS012345", id="gs3"),
        pytest.param("LINEA_GS012345", id="linea"),
        pytest.param("LINEAR_GS012345", id="linear"),
    ],
)
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    ble_name: str,
) -> None:
    """Testing reconfgure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await __do_successful_user_step(hass, result, mock_cloud_client)
    service_info = get_bluetooth_service_info(ModelName.GS3_MP, "GS012345")
    service_info.name = ble_name

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


async def test_reconfigure_flow_accept_policy(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the privacy policy is accepted during reconfigure."""
    mock_config_entry.add_to_hass(hass)
    mock_cloud_client.list_things.side_effect = [
        PolicyAcceptanceRequired(""),
        mock_cloud_client.list_things.return_value,
    ]

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**USER_INPUT, CONF_PASSWORD: "new_password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "accept_policy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE_POLICY: False, CONF_COMMERCIAL_POLICY: True},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "machine_selection"

    with patch(
        "homeassistant.components.lamarzocco.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MACHINE: "GS012345"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    mock_cloud_client.accept_privacy_policy.assert_awaited_once_with(
        profile_policy=False, commercial_policy=True
    )
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"


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
        CONF_INSTALLATION_KEY: MOCK_INSTALLATION_KEY,
    }
    assert result["result"].unique_id == "GS012345"


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
        CONF_INSTALLATION_KEY: MOCK_INSTALLATION_KEY,
    }


async def test_bluetooth_discovery_accept_policy_machine_not_found(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_cloud_client: MagicMock,
) -> None:
    """Test discovery aborts when the machine is missing after accepting the policy."""
    service_info = get_bluetooth_service_info(
        ModelName.GS3_MP, mock_lamarzocco.serial_number
    )
    things = deepcopy(mock_cloud_client.list_things.return_value)
    things[0].serial_number = "GS98765"
    mock_cloud_client.list_things.side_effect = [PolicyAcceptanceRequired(""), things]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=service_info,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "accept_policy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE_POLICY: False, CONF_COMMERCIAL_POLICY: False},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "machine_not_found"


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
            macaddress="aabbccddeeff",
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
        CONF_ADDRESS: "aabbccddeeff",
        CONF_TOKEN: None,
        CONF_INSTALLATION_KEY: MOCK_INSTALLATION_KEY,
    }
    assert result["result"].unique_id == "GS012345"


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
            macaddress="000000000000",
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
            macaddress="aabbccddeeff",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_config_entry.data[CONF_ADDRESS] != old_address
    assert mock_config_entry.data[CONF_ADDRESS] == "aabbccddeeff"


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
        CONF_OFFLINE_MODE: False,
    }


async def test_options_flow_bluetooth_required_for_offline_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow validates BT is required for offline mode."""
    await async_init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_USE_BLUETOOTH: False,
            CONF_OFFLINE_MODE: True,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {CONF_USE_BLUETOOTH: "bluetooth_required_offline"}

    # recover
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_USE_BLUETOOTH: True,
            CONF_OFFLINE_MODE: True,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_USE_BLUETOOTH: True,
        CONF_OFFLINE_MODE: True,
    }
