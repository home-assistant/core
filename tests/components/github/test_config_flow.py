"""Test the GitHub config flow."""
import json

from aiogithubapi import AIOGitHubAPIAuthenticationException, AIOGitHubAPIException
from aiogithubapi.objects.repository import AIOGitHubAPIRepository

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.github.const import (
    CONF_CLONES,
    CONF_ISSUES_PRS,
    CONF_LATEST_COMMIT,
    CONF_LATEST_RELEASE,
    CONF_REPOSITORY,
    CONF_VIEWS,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from tests.async_mock import patch
from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

FIXTURE_REAUTH_INPUT = {CONF_ACCESS_TOKEN: "abc234"}
FIXTURE_USER_INPUT = {
    CONF_ACCESS_TOKEN: "abc123",
    CONF_REPOSITORY: "octocat/Hello-World",
}
FIXTURE_OPTIONS_DEFAULT = {
    CONF_CLONES: False,
    CONF_ISSUES_PRS: False,
    CONF_LATEST_COMMIT: True,
    CONF_LATEST_RELEASE: False,
    CONF_VIEWS: False,
}
FIXTURE_OPTIONS_ALL = {
    CONF_CLONES: True,
    CONF_ISSUES_PRS: True,
    CONF_LATEST_COMMIT: True,
    CONF_LATEST_RELEASE: True,
    CONF_VIEWS: True,
}

UNIQUE_ID = "octocat/Hello-World"


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
        return_value=AIOGitHubAPIRepository(
            aioclient_mock, json.loads(load_fixture("github/repository.json"))
        ),
    ), patch(
        "homeassistant.components.github.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.github.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Hello-World"
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
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.github.config_flow.GitHub.get_repo",
        return_value=AIOGitHubAPIRepository(
            aioclient_mock, json.loads(load_fixture("github/repository.json"))
        ),
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
    assert result["errors"] == {}

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
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.github.config_flow.GitHub.get_repo",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_REAUTH_INPUT
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_find_repo"}


async def test_options_flow(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    """Test config flow options."""
    with patch(
        "homeassistant.components.github.config_flow.GitHub.get_repo",
        return_value=AIOGitHubAPIRepository(
            aioclient_mock, json.loads(load_fixture("github/repository.json"))
        ),
    ), patch("homeassistant.components.github.async_setup", return_value=True), patch(
        "homeassistant.components.github.async_setup_entry", return_value=True,
    ):
        mock_config = MockConfigEntry(
            domain=DOMAIN, unique_id=UNIQUE_ID, data=FIXTURE_USER_INPUT
        )
        mock_config.add_to_hass(hass)
        await hass.async_block_till_done()

        result2 = await hass.config_entries.options.async_init(mock_config.entry_id)

        assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
        # assert result2["step_id"] == "init"

        # result3 = await hass.config_entries.options.async_configure(
        #     result2["flow_id"], user_input=FIXTURE_OPTIONS_ALL
        # )

        # assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        # assert config_entry.options == FIXTURE_OPTIONS_ALL
