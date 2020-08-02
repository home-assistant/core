"""Test the GitHub config flow."""
from aiogithubapi import AIOGitHubAPIAuthenticationException, AIOGitHubAPIException
from aiogithubapi.objects.repository import AIOGitHubAPIRepository

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.github.const import CONF_REPOSITORY, DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from tests.async_mock import patch
from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

FIXTURE_REAUTH_INPUT = {CONF_ACCESS_TOKEN: "abc234"}
FIXTURE_USER_INPUT = {CONF_ACCESS_TOKEN: "abc123", CONF_REPOSITORY: "test/repo"}

UNIQUE_ID = "test/repo"


async def test_form(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.github.config_flow.GitHub.get_repo",
        return_value=AIOGitHubAPIRepository(aioclient_mock, {"name": "repo"}),
    ), patch(
        "homeassistant.components.github.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.github.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "repo"
    assert result2["data"] == FIXTURE_USER_INPUT
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.github.config_flow.GitHub.get_repo",
        side_effect=AIOGitHubAPIAuthenticationException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.github.config_flow.GitHub.get_repo",
        side_effect=AIOGitHubAPIException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_find_repo(hass: HomeAssistant):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.github.config_flow.GitHub.get_repo",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_find_repo"}


async def test_reauth_form(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    """Test we get the reauth form."""
    with patch(
        "homeassistant.components.github.config_flow.GitHub.get_repo",
        side_effect=AIOGitHubAPIAuthenticationException,
    ):
        mock_config = MockConfigEntry(
            domain=DOMAIN, unique_id=UNIQUE_ID, data=FIXTURE_USER_INPUT
        )
        mock_config.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reauth"}, data=FIXTURE_USER_INPUT
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth"
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.github.config_flow.GitHub.get_repo",
        return_value=AIOGitHubAPIRepository(aioclient_mock, {"name": "repo"}),
    ), patch("homeassistant.components.github.async_setup", return_value=True), patch(
        "homeassistant.components.github.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_REAUTH_INPUT
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result2["reason"] == "reauth_successful"


async def test_reauth_form_cannot_connect(hass: HomeAssistant):
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.github.config_flow.GitHub.get_repo",
        side_effect=AIOGitHubAPIAuthenticationException,
    ):
        mock_config = MockConfigEntry(
            domain=DOMAIN, unique_id=UNIQUE_ID, data=FIXTURE_USER_INPUT
        )
        mock_config.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reauth"}, data=FIXTURE_USER_INPUT
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth"
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.github.config_flow.GitHub.get_repo",
        side_effect=AIOGitHubAPIException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_REAUTH_INPUT
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_form_cannot_find_repo(hass: HomeAssistant):
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.github.config_flow.GitHub.get_repo",
        side_effect=AIOGitHubAPIAuthenticationException,
    ):
        mock_config = MockConfigEntry(
            domain=DOMAIN, unique_id=UNIQUE_ID, data=FIXTURE_USER_INPUT
        )
        mock_config.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reauth"}, data=FIXTURE_USER_INPUT
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth"
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.github.config_flow.GitHub.get_repo",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_REAUTH_INPUT
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_find_repo"}
