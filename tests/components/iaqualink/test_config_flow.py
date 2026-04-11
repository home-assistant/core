"""Tests for iAqualink config flow."""

from unittest.mock import MagicMock, patch

from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)
import pytest

from homeassistant.components.iaqualink import DOMAIN, config_flow
from homeassistant.components.iaqualink.const import CONF_SYSTEMS
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_data: dict[str, str],
) -> None:
    """Test config flow when iaqualink component is already setup."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_without_config(hass: HomeAssistant) -> None:
    """Test config flow with no configuration."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_user()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_with_invalid_credentials(
    hass: HomeAssistant, config_data: dict[str, str]
) -> None:
    """Test config flow with invalid username and/or password."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.iaqualink.utils.AqualinkClient.login",
        side_effect=AqualinkServiceUnauthorizedException,
    ):
        result = await flow.async_step_user(config_data)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_service_exception(
    hass: HomeAssistant, config_data: dict[str, str]
) -> None:
    """Test config flow encountering service exception."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.iaqualink.utils.AqualinkClient.login",
        side_effect=AqualinkServiceException,
    ):
        result = await flow.async_step_user(config_data)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_timeout_during_credential_check(
    hass: HomeAssistant, config_data: dict[str, str]
) -> None:
    """Test config flow maps login timeout to cannot_connect."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.iaqualink.utils.AqualinkClient.login",
        side_effect=TimeoutError,
    ):
        result = await flow.async_step_user(config_data)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_with_existing_config(
    hass: HomeAssistant, config_data: dict[str, str]
) -> None:
    """Test config flow with existing configuration."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass
    flow.context = {}

    mock_system1 = MagicMock()
    mock_system1.serial = "SN001"
    mock_system1.name = "Pool System 1"

    mock_system2 = MagicMock()
    mock_system2.serial = "SN002"
    mock_system2.name = "Pool System 2"

    with (
        patch(
            "homeassistant.components.iaqualink.utils.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.config_flow.async_get_systems",
            return_value=(
                {
                    "SN001": mock_system1,
                    "SN002": mock_system2,
                },
                None,
            ),
        ),
    ):
        result = await flow.async_step_user(config_data)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "systems"

    result = await flow.async_step_systems({"systems": ["SN001"]})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == config_data["username"]
    assert result["data"] == config_data
    assert result["options"] == {"systems": ["SN001"]}


async def test_with_no_systems(
    hass: HomeAssistant, config_data: dict[str, str]
) -> None:
    """Test config flow when the account returns no systems."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass

    with (
        patch(
            "homeassistant.components.iaqualink.utils.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.utils.AqualinkClient.get_systems",
            return_value={},
        ),
    ):
        result = await flow.async_step_user(config_data)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_systems"}


async def test_timeout_during_system_fetch(
    hass: HomeAssistant, config_data: dict[str, str]
) -> None:
    """Test config flow maps system fetch timeout to cannot_connect."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass

    with (
        patch(
            "homeassistant.components.iaqualink.utils.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.utils.AqualinkClient.get_systems",
            side_effect=TimeoutError,
        ),
    ):
        result = await flow.async_step_user(config_data)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_async_get_systems_success(
    hass: HomeAssistant,
    config_data: dict[str, str],
) -> None:
    """Test async_get_systems returns systems on success."""
    mock_system = MagicMock()
    mock_system.serial = "SN001"
    mock_system.name = "Pool System 1"

    with (
        patch(
            "homeassistant.components.iaqualink.utils.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.utils.AqualinkClient.get_systems",
            return_value={"SN001": mock_system},
        ),
    ):
        systems, error_reason = await config_flow.async_get_systems(
            hass,
            config_data[CONF_USERNAME],
            config_data[CONF_PASSWORD],
        )

    assert systems == {"SN001": mock_system}
    assert error_reason is None


async def test_systems_step_without_pending_user_input(
    hass: HomeAssistant,
) -> None:
    """Test systems step falls back to the initial form without saved state."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_systems()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_reauth_success(hass: HomeAssistant, config_data: dict[str, str]) -> None:
    """Test successful reauthentication."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=config_data[CONF_USERNAME],
        data=config_data,
    )
    entry.add_to_hass(hass)

    new_username = "updated@example.com"

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.iaqualink.utils.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: new_username, CONF_PASSWORD: "new_password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.title == new_username
    assert dict(entry.data) == {
        **config_data,
        CONF_USERNAME: new_username,
        CONF_PASSWORD: "new_password",
    }


async def test_reauth_invalid_auth(
    hass: HomeAssistant, config_data: dict[str, str]
) -> None:
    """Test reauthentication with invalid credentials."""
    entry = MockConfigEntry(domain=DOMAIN, data=config_data)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.iaqualink.utils.AqualinkClient.login",
        side_effect=AqualinkServiceUnauthorizedException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: config_data[CONF_USERNAME], CONF_PASSWORD: "bad_password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_cannot_connect(
    hass: HomeAssistant, config_data: dict[str, str]
) -> None:
    """Test reauthentication when the service cannot be reached."""
    entry = MockConfigEntry(domain=DOMAIN, data=config_data)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.iaqualink.utils.AqualinkClient.login",
        side_effect=AqualinkServiceException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: config_data[CONF_USERNAME], CONF_PASSWORD: "new_password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow_init_success(
    hass: HomeAssistant, config_data: dict[str, str]
) -> None:
    """Test options flow initializes and displays systems."""
    entry = MockConfigEntry(domain=DOMAIN, data=config_data)
    entry.add_to_hass(hass)

    # Mock systems
    mock_system1 = MagicMock()
    mock_system1.serial = "SN001"
    mock_system1.name = "Pool System 1"

    mock_system2 = MagicMock()
    mock_system2.serial = "SN002"
    mock_system2.name = "Pool System 2"

    with patch(
        "homeassistant.components.iaqualink.config_flow.async_get_systems",
        return_value=(
            {
                "SN001": mock_system1,
                "SN002": mock_system2,
            },
            None,
        ),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_submit_systems(
    hass: HomeAssistant, config_data: dict[str, str]
) -> None:
    """Test options flow submits selected systems."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        options={},
    )
    entry.add_to_hass(hass)

    # Mock systems
    mock_system1 = MagicMock()
    mock_system1.serial = "SN001"
    mock_system1.name = "Pool System 1"

    mock_system2 = MagicMock()
    mock_system2.serial = "SN002"
    mock_system2.name = "Pool System 2"

    with patch(
        "homeassistant.components.iaqualink.config_flow.async_get_systems",
        return_value=(
            {
                "SN001": mock_system1,
                "SN002": mock_system2,
            },
            None,
        ),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)

        # Submit form with only SN001 selected
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_SYSTEMS: ["SN001"]},
        )

    assert entry.options[CONF_SYSTEMS] == ["SN001"]


async def test_options_flow_submit_systems_direct_init_call(
    hass: HomeAssistant, config_data: dict[str, str]
) -> None:
    """Test options flow can submit directly when started with user input."""
    entry = MockConfigEntry(domain=DOMAIN, data=config_data)
    entry.add_to_hass(hass)

    flow = config_flow.AqualinkOptionsFlowHandler()
    flow.hass = hass
    flow.handler = entry.entry_id

    mock_system = MagicMock()
    mock_system.serial = "SN001"
    mock_system.name = "Pool System 1"

    with patch(
        "homeassistant.components.iaqualink.config_flow.async_get_systems",
        return_value=({"SN001": mock_system}, None),
    ):
        result = await flow.async_step_init({CONF_SYSTEMS: ["SN001"]})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_SYSTEMS: ["SN001"]}


@pytest.mark.parametrize(
    ("get_systems_result", "reason"),
    [
        (AqualinkServiceUnauthorizedException, "invalid_auth"),
        (AqualinkServiceException, "cannot_connect"),
        ({}, "no_systems"),
    ],
)
async def test_options_flow_init_abort_reasons(
    hass: HomeAssistant,
    config_data: dict[str, str],
    get_systems_result: type[Exception] | dict[str, str],
    reason: str,
) -> None:
    """Test options flow displays errors when systems cannot be loaded."""
    entry = MockConfigEntry(domain=DOMAIN, data=config_data)
    entry.add_to_hass(hass)

    get_systems_patch = patch(
        "homeassistant.components.iaqualink.utils.AqualinkClient.get_systems",
        side_effect=get_systems_result,
    )
    if isinstance(get_systems_result, dict):
        get_systems_patch = patch(
            "homeassistant.components.iaqualink.utils.AqualinkClient.get_systems",
            return_value=get_systems_result,
        )

    with (
        patch(
            "homeassistant.components.iaqualink.utils.AqualinkClient.login",
            return_value=None,
        ),
        get_systems_patch,
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": reason}
