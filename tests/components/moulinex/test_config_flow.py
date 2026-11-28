"""Tests for the Moulinex config flow."""

from unittest.mock import ANY, AsyncMock

from aiomoulinex import (
    COUNTRIES,
    LoginError,
    LoginFailure,
    MoulinexAuthenticationError,
    MoulinexConnectionError,
    MoulinexError,
    Profile,
    Region,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.moulinex.const import CONF_TOKENS, DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_COUNTRY, CONF_EMAIL, CONF_PASSWORD, CONF_REGION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.translation import async_get_translations

from .conftest import EMAIL, USER_ID, build_tokens

PASSWORD = "test-password"
DHCP_DISCOVERY = DhcpServiceInfo(
    ip="192.168.1.20", hostname="seb_product_1a2b", macaddress="aabbccdd1a2b"
)
USER_INPUT = {
    CONF_COUNTRY: "FR",
    CONF_EMAIL: EMAIL,
    CONF_PASSWORD: PASSWORD,
}
SWISS_USER_INPUT = {**USER_INPUT, CONF_COUNTRY: "CH"}

ERRORS = [
    *(
        pytest.param("mock_login", LoginError(reason), reason.value, id=reason.value)
        for reason in LoginFailure
    ),
    pytest.param(
        "mock_login",
        MoulinexConnectionError("timeout"),
        "cannot_connect",
        id="login_cannot_connect",
    ),
    pytest.param(
        "mock_login", MoulinexError("unexpected"), "unknown", id="login_unknown"
    ),
    pytest.param(
        "mock_fetch_profile",
        MoulinexAuthenticationError("refused"),
        "invalid_auth",
        id="profile_refused",
    ),
    pytest.param(
        "mock_fetch_profile",
        MoulinexConnectionError("timeout"),
        "cannot_connect",
        id="profile_cannot_connect",
    ),
]


async def test_regions_are_translated(hass: HomeAssistant) -> None:
    """Every region of a country with several regions has a label."""
    translations = await async_get_translations(hass, "en", "selector", {DOMAIN})

    assert {
        f"component.{DOMAIN}.selector.region.options.{region}"
        for country in COUNTRIES
        if len(regions := Region.for_country(country)) > 1
        for region in regions
    } <= translations.keys()


@pytest.mark.parametrize(
    ("country", "suggested"),
    [
        pytest.param("FR", "FR", id="known"),
        pytest.param("US", None, id="unknown"),
    ],
)
async def test_user_form_suggests_country(
    hass: HomeAssistant, country: str, suggested: str | None
) -> None:
    """The country of Home Assistant is suggested when a region serves it."""
    hass.config.country = country

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    schema_key = next(
        key for key in result["data_schema"].schema if key == CONF_COUNTRY
    )
    assert (schema_key.description or {}).get("suggested_value") == suggested


@pytest.mark.usefixtures("mock_fetch_profile")
async def test_user_flow(
    hass: HomeAssistant, mock_login: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """The user logs in and the account is set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["data"] == {
        CONF_REGION: Region.MOULINEX_FR,
        CONF_EMAIL: EMAIL,
        CONF_TOKENS: build_tokens().to_dict(),
    }
    assert result["result"].unique_id == USER_ID
    mock_login.assert_awaited_once_with(ANY, EMAIL, PASSWORD, Region.MOULINEX_FR)
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("source", "discovery_info"),
    [
        pytest.param(SOURCE_USER, None, id="user"),
        pytest.param(SOURCE_DHCP, DHCP_DISCOVERY, id="dhcp"),
    ],
)
@pytest.mark.parametrize(("failing", "exception", "error"), ERRORS)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_login: AsyncMock,
    mock_fetch_profile: AsyncMock,
    source: str,
    discovery_info: DhcpServiceInfo | None,
    failing: str,
    exception: Exception,
    error: str,
) -> None:
    """Each error is shown on the form, and the user can try again."""
    mock = {"mock_login": mock_login, "mock_fetch_profile": mock_fetch_profile}[failing]
    mock.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=discovery_info
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_login", "mock_fetch_profile")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """An account can only be set up once."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_login", "mock_fetch_profile")
async def test_dhcp_discovery(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """An appliance found on the network leads to the login form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["result"].unique_id == USER_ID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """An appliance found on the network is ignored once an account is set up."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_login", "mock_setup_entry")
async def test_user_flow_no_appliances(
    hass: HomeAssistant, mock_fetch_profile: AsyncMock, mock_profile: Profile
) -> None:
    """An account without an appliance in the region is not set up."""
    mock_fetch_profile.return_value = Profile()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_appliances"}

    mock_fetch_profile.return_value = mock_profile
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_fetch_profile")
async def test_user_flow_region(
    hass: HomeAssistant, mock_login: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """The user picks the region of a country served by several regions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], SWISS_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"] == {}
    mock_login.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_REGION: Region.KRUPS_DE}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_REGION: Region.KRUPS_DE,
        CONF_EMAIL: EMAIL,
        CONF_TOKENS: build_tokens().to_dict(),
    }
    assert result["result"].unique_id == USER_ID
    mock_login.assert_awaited_once_with(ANY, EMAIL, PASSWORD, Region.KRUPS_DE)
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_fetch_profile", "mock_setup_entry")
async def test_user_flow_region_login_error(
    hass: HomeAssistant, mock_login: AsyncMock
) -> None:
    """A login error after picking the region leads back to the login form."""
    mock_login.side_effect = MoulinexAuthenticationError("refused")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], SWISS_USER_INPUT
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_REGION: Region.MOULINEX_CH}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    mock_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], SWISS_USER_INPUT
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_REGION: Region.MOULINEX_CH}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USER_ID


@pytest.mark.usefixtures("mock_login", "mock_setup_entry")
async def test_user_flow_region_no_appliances(
    hass: HomeAssistant, mock_fetch_profile: AsyncMock, mock_profile: Profile
) -> None:
    """The user can pick another region when the first one has no appliance."""
    mock_fetch_profile.return_value = Profile()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], SWISS_USER_INPUT
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_REGION: Region.MOULINEX_CH}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"] == {"base": "no_appliances"}

    mock_fetch_profile.return_value = mock_profile
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_REGION: Region.MOULINEX_FR}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_REGION] == Region.MOULINEX_FR
