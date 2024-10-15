"""Test the HTML5 config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.html5.const import (
    ATTR_VAPID_EMAIL,
    ATTR_VAPID_PRV_KEY,
    ATTR_VAPID_PUB_KEY,
    DOMAIN,
)
from homeassistant.components.html5.issues import (
    FAILED_IMPORT_TRANSLATION_KEY,
    SUCCESSFUL_IMPORT_TRANSLATION_KEY,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.issue_registry as ir

MOCK_CONF = {
    ATTR_VAPID_EMAIL: "test@example.com",
    ATTR_VAPID_PRV_KEY: "h6acSRds8_KR8hT9djD8WucTL06Gfe29XXyZ1KcUjN8",
}
MOCK_CONF_PUB_KEY = "BIUtPN7Rq_8U7RBEqClZrfZ5dR9zPCfvxYPtLpWtRVZTJEc7lzv2dhzDU6Aw1m29Ao0-UA1Uq6XO9Df8KALBKqA"


async def test_step_user_success(hass: HomeAssistant) -> None:
    """Test a successful user config flow."""

    with patch(
        "homeassistant.components.html5.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_CONF.copy(),
        )

        await hass.async_block_till_done()

        assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            ATTR_VAPID_PRV_KEY: MOCK_CONF[ATTR_VAPID_PRV_KEY],
            ATTR_VAPID_PUB_KEY: MOCK_CONF_PUB_KEY,
            ATTR_VAPID_EMAIL: MOCK_CONF[ATTR_VAPID_EMAIL],
            CONF_NAME: DOMAIN,
        }

        assert mock_setup_entry.call_count == 1


async def test_step_user_success_generate(hass: HomeAssistant) -> None:
    """Test a successful user config flow, generating a key pair."""

    with patch(
        "homeassistant.components.html5.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        conf = {ATTR_VAPID_EMAIL: MOCK_CONF[ATTR_VAPID_EMAIL]}
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
        )

        await hass.async_block_till_done()

        assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"][ATTR_VAPID_EMAIL] == MOCK_CONF[ATTR_VAPID_EMAIL]

        assert mock_setup_entry.call_count == 1


async def test_step_user_new_form(hass: HomeAssistant) -> None:
    """Test new user input."""

    with patch(
        "homeassistant.components.html5.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
        )

        await hass.async_block_till_done()

        assert result["type"] is data_entry_flow.FlowResultType.FORM
        assert mock_setup_entry.call_count == 0

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONF
        )
        assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
        assert mock_setup_entry.call_count == 1


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (ATTR_VAPID_PRV_KEY, "invalid"),
    ],
)
async def test_step_user_form_invalid_key(
    hass: HomeAssistant, key: str, value: str
) -> None:
    """Test invalid user input."""

    with patch(
        "homeassistant.components.html5.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        bad_conf = MOCK_CONF.copy()
        bad_conf[key] = value

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=bad_conf
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert mock_setup_entry.call_count == 0

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONF
        )
        assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
        assert mock_setup_entry.call_count == 1


async def test_step_import_good(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test valid import input."""

    with (
        patch(
            "homeassistant.components.html5.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        conf = MOCK_CONF.copy()
        conf[ATTR_VAPID_PUB_KEY] = MOCK_CONF_PUB_KEY
        conf["random_key"] = "random_value"

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=conf
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            ATTR_VAPID_PRV_KEY: conf[ATTR_VAPID_PRV_KEY],
            ATTR_VAPID_PUB_KEY: MOCK_CONF_PUB_KEY,
            ATTR_VAPID_EMAIL: conf[ATTR_VAPID_EMAIL],
            CONF_NAME: DOMAIN,
        }

        assert mock_setup_entry.call_count == 1
        assert len(issue_registry.issues) == 1
        issue = issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
        )
        assert issue
        assert issue.translation_key == SUCCESSFUL_IMPORT_TRANSLATION_KEY


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (ATTR_VAPID_PRV_KEY, "invalid"),
    ],
)
async def test_step_import_bad(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, key: str, value: str
) -> None:
    """Test invalid import input."""

    with (
        patch(
            "homeassistant.components.html5.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        bad_conf = MOCK_CONF.copy()
        bad_conf[key] = value

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=bad_conf
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert mock_setup_entry.call_count == 0

        assert len(issue_registry.issues) == 1
        issue = issue_registry.async_get_issue(DOMAIN, f"deprecated_yaml_{DOMAIN}")
        assert issue
        assert issue.translation_key == FAILED_IMPORT_TRANSLATION_KEY
