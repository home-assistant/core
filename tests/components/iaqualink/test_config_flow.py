"""Tests for iAquaLink config flow."""

from unittest.mock import patch

from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)

from homeassistant.components.iaqualink import DOMAIN, config_flow
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry

DHCP_DISCOVERY = DhcpServiceInfo(
    ip="192.168.1.23",
    hostname="iaqualink-123456",
    macaddress="001122334455",
)


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


async def test_dhcp_discovery_starts_user_flow(
    hass: HomeAssistant, config_data: dict[str, str]
) -> None:
    """Test DHCP discovery starts the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    assert result["description_placeholders"] is None

    with (
        patch(
            "homeassistant.components.iaqualink.config_flow.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            config_data,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == config_data[CONF_USERNAME]
    assert result["data"] == config_data


async def test_with_invalid_credentials(
    hass: HomeAssistant, config_data: dict[str, str]
) -> None:
    """Test config flow with invalid username and/or password."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass
    flow.context = {}

    with patch(
        "homeassistant.components.iaqualink.config_flow.AqualinkClient.login",
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
        "homeassistant.components.iaqualink.config_flow.AqualinkClient.login",
        side_effect=AqualinkServiceException,
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

    with patch(
        "homeassistant.components.iaqualink.config_flow.AqualinkClient.login",
        return_value=None,
    ):
        result = await flow.async_step_user(config_data)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == config_data["username"]
    assert result["data"] == config_data


async def test_dhcp_discovery_aborts_if_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery aborts if iaqualink is already configured."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


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
            "homeassistant.components.iaqualink.config_flow.AqualinkClient.login",
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
        "homeassistant.components.iaqualink.config_flow.AqualinkClient.login",
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
        "homeassistant.components.iaqualink.config_flow.AqualinkClient.login",
        side_effect=AqualinkServiceException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: config_data[CONF_USERNAME], CONF_PASSWORD: "new_password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "cannot_connect"}
