"""Tests for the SMTP integration."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.smtp.const import (
    CONF_ENCRYPTION,
    CONF_SENDER_NAME,
    CONF_SERVER,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_DEBUG,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("smtp")
async def test_entry_setup_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test integration setup and unload."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("smtp")
async def test_import(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test yaml import."""

    await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_NAME: "notifier_name",
                    CONF_SENDER: "email@example.com",
                    CONF_SENDER_NAME: "Home Assistant",
                    CONF_SERVER: "mail.example.com",
                    CONF_PORT: 587,
                    CONF_ENCRYPTION: "starttls",
                    CONF_USERNAME: "test-username",
                    CONF_PASSWORD: "test-password",
                    CONF_VERIFY_SSL: True,
                    CONF_RECIPIENT: "recipient@example.com",
                    CONF_DEBUG: True,
                    CONF_TIMEOUT: 10,
                }
            ]
        },
    )

    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(entries := hass.config_entries.async_entries(DOMAIN)) == 1

    assert len(entries[0].subentries) == 1

    assert entries[0].title == "notifier_name"
    assert entries[0].data == {
        CONF_PLATFORM: DOMAIN,
        CONF_NAME: "notifier_name",
        CONF_SENDER: "email@example.com",
        CONF_SENDER_NAME: "Home Assistant",
        CONF_SERVER: "mail.example.com",
        CONF_PORT: 587,
        CONF_ENCRYPTION: "starttls",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_VERIFY_SSL: True,
        CONF_RECIPIENT: ["recipient@example.com"],
    }
    assert entries[0].options == {
        CONF_TIMEOUT: 10,
        CONF_DEBUG: True,
    }

    assert list(entries[0].subentries.values())[0].unique_id == "recipient@example.com"

    assert issue_registry.async_get_issue(
        domain=HOMEASSISTANT_DOMAIN,
        issue_id=f"deprecated_yaml_{DOMAIN}",
    )


@pytest.mark.usefixtures("smtp")
async def test_import_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test yaml import aborts if already configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home Assistant",
        data={
            CONF_PLATFORM: DOMAIN,
            CONF_NAME: "notifier_name",
            CONF_SENDER: "email@example.com",
            CONF_SENDER_NAME: "Home Assistant",
            CONF_SERVER: "mail.example.com",
            CONF_PORT: 587,
            CONF_ENCRYPTION: "starttls",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_VERIFY_SSL: True,
            CONF_RECIPIENT: ["recipient@example.com"],
        },
        entry_id="123456789",
    )

    config_entry.add_to_hass(hass)

    await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_NAME: "notifier_name",
                    CONF_SENDER: "email@example.com",
                    CONF_SENDER_NAME: "Home Assistant",
                    CONF_SERVER: "mail.example.com",
                    CONF_PORT: 587,
                    CONF_ENCRYPTION: "starttls",
                    CONF_USERNAME: "test-username",
                    CONF_PASSWORD: "test-password",
                    CONF_VERIFY_SSL: True,
                    CONF_RECIPIENT: "recipient@example.com",
                }
            ]
        },
    )

    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 0
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert issue_registry.async_get_issue(
        domain=HOMEASSISTANT_DOMAIN,
        issue_id=f"deprecated_yaml_{DOMAIN}",
    )


async def test_import_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    issue_registry: ir.IssueRegistry,
    smtp: MagicMock,
) -> None:
    """Test yaml triggers import flow, aborts with errors, and creates error issue."""
    smtp.login.side_effect = ValueError

    await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_NAME: "notifier_name",
                    CONF_SENDER: "email@example.com",
                    CONF_SENDER_NAME: "Home Assistant",
                    CONF_SERVER: "mail.example.com",
                    CONF_PORT: 587,
                    CONF_ENCRYPTION: "starttls",
                    CONF_USERNAME: "test-username",
                    CONF_PASSWORD: "test-password",
                    CONF_VERIFY_SSL: True,
                    CONF_RECIPIENT: "recipient@example.com",
                }
            ]
        },
    )

    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 0
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0

    assert not issue_registry.async_get_issue(
        domain=HOMEASSISTANT_DOMAIN,
        issue_id=f"deprecated_yaml_{DOMAIN}",
    )
    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=(
            "deprecated_yaml_import_issue_error_notifier_name"
            "_email@example.com_mail.example.com"
        ),
    )
