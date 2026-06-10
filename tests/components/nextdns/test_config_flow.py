"""Define tests for the NextDNS config flow."""

from types import MappingProxyType
from unittest.mock import AsyncMock

from nextdns import ApiError, InvalidApiKeyError, ProfileInfo
import pytest
from tenacity import RetryError

from homeassistant.components.nextdns.const import (
    CONF_PROFILE_ID,
    DOMAIN,
    SUBENTRY_TYPE_PROFILE,
)
from homeassistant.config_entries import SOURCE_USER, ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_PROFILE_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import init_integration

from tests.common import MockConfigEntry


async def test_form_create_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_nextdns_client: AsyncMock,
    mock_nextdns: AsyncMock,
) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "fake_api_key"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "profiles"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PROFILE_NAME: "Fake Profile"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NextDNS"
    assert result["data"][CONF_API_KEY] == "fake_api_key"
    assert len(result["subentries"]) == 1
    subentry = result["subentries"][0]
    assert subentry["subentry_type"] == SUBENTRY_TYPE_PROFILE
    assert subentry["title"] == "Fake Profile"
    assert subentry["data"][CONF_PROFILE_ID] == "xyz12"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (ApiError("API Error"), "cannot_connect"),
        (InvalidApiKeyError, "invalid_api_key"),
        (RetryError("Retry Error"), "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_nextdns_client: AsyncMock,
    mock_nextdns: AsyncMock,
    exc: Exception,
    base_error: str,
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_nextdns.create.side_effect = exc

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "fake_api_key"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base_error}

    mock_nextdns.create.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "fake_api_key"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "profiles"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PROFILE_NAME: "Fake Profile"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NextDNS"
    assert result["data"][CONF_API_KEY] == "fake_api_key"
    assert len(result["subentries"]) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
    mock_nextdns: AsyncMock,
) -> None:
    """Test that the flow aborts when API key is already configured."""
    await init_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "fake_api_key"},
    )

    # When a config entry with the same API key exists, the flow aborts
    # Users should add profiles via the subentry flow
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_successful(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
    mock_nextdns: AsyncMock,
) -> None:
    """Test starting a reauthentication flow."""
    await init_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"


async def test_reauth_no_profile(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test reauthentication flow when the profile is no longer available."""
    await init_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_nextdns_client.profiles = [
        ProfileInfo(id="abcd098", fingerprint="abcd098", name="New Profile")
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "profile_not_available"


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (ApiError("API Error"), "cannot_connect"),
        (InvalidApiKeyError, "invalid_api_key"),
        (RetryError("Retry Error"), "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    exc: Exception,
    base_error: str,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
    mock_nextdns: AsyncMock,
) -> None:
    """Test reauthentication flow with errors."""
    await init_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_nextdns.create.side_effect = exc

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )

    assert result["errors"] == {"base": base_error}

    mock_nextdns.create.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test starting a reconfigure flow."""
    await init_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (ApiError("API Error"), "cannot_connect"),
        (InvalidApiKeyError, "invalid_api_key"),
        (RetryError("Retry Error"), "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_reconfiguration_errors(
    hass: HomeAssistant,
    exc: Exception,
    base_error: str,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
    mock_nextdns: AsyncMock,
) -> None:
    """Test reconfigure flow with errors."""
    await init_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_nextdns.create.side_effect = exc

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )

    assert result["errors"] == {"base": base_error}

    mock_nextdns.create.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"


async def test_reconfigure_flow_no_profile(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test reconfigure flow when the profile is no longer available."""
    await init_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_nextdns_client.profiles = [
        ProfileInfo(id="abcd098", fingerprint="abcd098", name="New Profile")
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "profile_not_available"


async def test_subentry_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test creating a profile subentry."""
    # Add a second profile to the client
    mock_nextdns_client.profiles = [
        ProfileInfo(id="xyz12", fingerprint="xyz12", name="Fake Profile"),
        ProfileInfo(id="abc34", fingerprint="abc34", name="Second Profile"),
    ]
    mock_nextdns_client.get_profile_id = lambda name: (
        "abc34" if name == "Second Profile" else "xyz12"
    )

    await init_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PROFILE),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_PROFILE_NAME: "Second Profile"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Second Profile"
    assert result["data"][CONF_PROFILE_ID] == "abc34"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert len(entry.subentries) == 2


async def test_subentry_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test subentry flow when the profile gets configured between form display and submit."""
    # Add a second and third profile so the flow doesn't abort immediately
    second_profile = ProfileInfo(
        id="abc34", fingerprint="xyz789", name="Second Profile"
    )
    third_profile = ProfileInfo(id="def56", fingerprint="uvw456", name="Third Profile")
    mock_nextdns_client.profiles = [
        *mock_nextdns_client.profiles,
        second_profile,
        third_profile,
    ]

    await init_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PROFILE),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Simulate a race condition where the second profile gets configured
    # between showing the form and submitting it
    hass.config_entries.async_add_subentry(
        mock_config_entry,
        ConfigSubentry(
            data=MappingProxyType({CONF_PROFILE_ID: "abc34"}),
            subentry_type=SUBENTRY_TYPE_PROFILE,
            title="Second Profile",
            unique_id="abc34",
        ),
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_PROFILE_NAME: "Second Profile"},
    )

    # The form should be shown again with an error, and only "Third Profile" available
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "already_configured"


async def test_subentry_flow_all_profiles_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test subentry flow when all profiles are already configured."""
    await init_integration(hass, mock_config_entry)

    # Only one profile available and it's already configured
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PROFILE),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "all_profiles_configured"


async def test_subentry_flow_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test subentry flow when the entry is not loaded."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PROFILE),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"
