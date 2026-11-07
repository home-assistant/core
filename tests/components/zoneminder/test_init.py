"""Tests for ZoneMinder setup and YAML import."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    Timeout as RequestsTimeout,
)

from homeassistant.components.zoneminder.const import (
    CONF_INCLUDE_ARCHIVED,
    CONF_PATH_ZMS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryState
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import MOCK_CONFIG_DATA, MOCK_HOST, MOCK_HOST_2, MOCK_OPTIONS

YAML_CONFIG = {
    DOMAIN: [{CONF_HOST: MOCK_HOST, CONF_USERNAME: "admin", CONF_PASSWORD: "secret"}]
}


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up and unloading a config entry."""
    await setup_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_zoneminder_client.mock_cls.assert_called_once_with(
        f"http://{MOCK_HOST}", "admin", "secret", "/zm/", "/zm/cgi-bin/nph-zms", True
    )

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_https(
    hass: HomeAssistant, mock_zoneminder_client: MagicMock
) -> None:
    """Test the client uses https and the configured paths."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PATH: "/custom/",
            CONF_PATH_ZMS: "/custom/zms",
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
        options=MOCK_OPTIONS,
    )
    await setup_integration(hass, entry, [Platform.BINARY_SENSOR])

    mock_zoneminder_client.mock_cls.assert_called_once_with(
        f"https://{MOCK_HOST}", None, None, "/custom/", "/custom/zms", False
    )


@pytest.mark.parametrize(
    ("side_effect", "login", "monitors", "state"),
    [
        pytest.param(
            RequestsConnectionError,
            True,
            None,
            ConfigEntryState.SETUP_RETRY,
            id="refused",
        ),
        pytest.param(
            RequestsTimeout, True, None, ConfigEntryState.SETUP_RETRY, id="timeout"
        ),
        pytest.param(None, False, None, ConfigEntryState.SETUP_ERROR, id="bad_auth"),
        pytest.param(None, True, [], ConfigEntryState.SETUP_RETRY, id="no_monitors"),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception] | None,
    login: bool,
    monitors: list | None,
    state: ConfigEntryState,
) -> None:
    """Test setup failures set the matching config entry state."""
    mock_zoneminder_client.login.side_effect = side_effect
    mock_zoneminder_client.login.return_value = login
    mock_zoneminder_client.get_monitors.return_value = monitors

    await setup_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    assert mock_config_entry.state is state


@pytest.mark.usefixtures("mock_zoneminder_client")
async def test_yaml_import(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test each YAML server is imported and the deprecation issue is raised."""
    config = {
        DOMAIN: [
            *YAML_CONFIG[DOMAIN],
            {CONF_HOST: MOCK_HOST_2, CONF_SSL: True},
        ]
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert [(entry.source, entry.data) for entry in entries] == [
        (SOURCE_IMPORT, MOCK_CONFIG_DATA),
        (
            SOURCE_IMPORT,
            {
                CONF_HOST: MOCK_HOST_2,
                CONF_PATH: "/zm/",
                CONF_PATH_ZMS: "/zm/cgi-bin/nph-zms",
                CONF_SSL: True,
                CONF_VERIFY_SSL: True,
            },
        ),
    ]
    assert entries[0].options == MOCK_OPTIONS
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize(
    ("platform_config", "expected_options"),
    [
        pytest.param(
            {
                "sensor": [{"platform": DOMAIN, CONF_INCLUDE_ARCHIVED: True}],
                "switch": [
                    {
                        "platform": DOMAIN,
                        CONF_COMMAND_ON: "Record",
                        CONF_COMMAND_OFF: "None",
                    }
                ],
            },
            {
                CONF_INCLUDE_ARCHIVED: True,
                CONF_COMMAND_ON: "record",
                CONF_COMMAND_OFF: "none",
            },
            id="valid",
        ),
        pytest.param(
            {
                "sensor": [{"platform": "other", CONF_INCLUDE_ARCHIVED: True}],
                "switch": [{"platform": DOMAIN, CONF_COMMAND_ON: "Invalid"}],
            },
            MOCK_OPTIONS,
            id="invalid_or_other_platform",
        ),
    ],
)
@pytest.mark.usefixtures("mock_zoneminder_client")
async def test_yaml_import_platform_options(
    hass: HomeAssistant,
    platform_config: dict[str, Any],
    expected_options: dict[str, Any],
) -> None:
    """Test the sensor and switch platform YAML options are imported."""
    assert await async_setup_component(hass, DOMAIN, {**YAML_CONFIG, **platform_config})
    await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.options == expected_options


@pytest.mark.parametrize(
    ("side_effect", "login", "issue_id"),
    [
        pytest.param(
            RequestsConnectionError,
            True,
            "deprecated_yaml_import_issue_cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(
            None, False, "deprecated_yaml_import_issue_invalid_auth", id="invalid_auth"
        ),
    ],
)
async def test_yaml_import_failure(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    issue_registry: ir.IssueRegistry,
    side_effect: type[Exception] | None,
    login: bool,
    issue_id: str,
) -> None:
    """Test a failed YAML import raises an import issue instead."""
    mock_zoneminder_client.login.side_effect = side_effect
    mock_zoneminder_client.login.return_value = login

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("mock_zoneminder_client")
async def test_yaml_import_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an already imported server still raises the deprecation issue."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
