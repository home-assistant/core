"""Test the Remember The Milk integration."""

from unittest.mock import MagicMock

from aiortm import AioRTMError, AuthError
import pytest

from homeassistant.components.remember_the_milk.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .const import PROFILE

from tests.common import MockConfigEntry

CONFIG = {
    "name": "myprofile",
    "api_key": "test-api-key",
    "shared_secret": "test-shared-secret",
}


@pytest.mark.usefixtures("storage")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading a config entry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("storage")
@pytest.mark.parametrize(
    ("side_effect", "entry_state", "ignore_missing_translations"),
    [
        pytest.param(
            AuthError("Invalid token!"),
            ConfigEntryState.SETUP_ERROR,
            [
                f"component.{DOMAIN}.services.{PROFILE}_create_task.",
                f"component.{DOMAIN}.services.{PROFILE}_complete_task.",
            ],
            id="auth_error",
        ),
        pytest.param(
            AioRTMError("Connection failed!"),
            ConfigEntryState.SETUP_RETRY,
            [],
            id="rtm_error",
        ),
    ],
)
async def test_config_entry_check_token_fails(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    side_effect: Exception,
    entry_state: ConfigEntryState,
) -> None:
    """Test that token check failures put the entry in the expected state."""
    client.rtm.api.check_token.side_effect = side_effect

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is entry_state


@pytest.mark.usefixtures("client", "storage")
async def test_import_creates_deprecation_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a successful YAML import creates a deprecation repair issue."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: CONFIG})
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize("ignore_missing_translations", [[]])
@pytest.mark.usefixtures("client")
async def test_import_without_token_creates_issue(
    hass: HomeAssistant,
    storage: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import without a stored token aborts and creates an issue.

    Without a token the import can't be completed, so no config entry is
    created and the user is guided to set the integration up via the UI.
    """
    storage.get_token.return_value = None

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: CONFIG})
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_invalid_auth"
    )
