"""Test the Twilio config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.twilio.const import DOMAIN
from homeassistant.config import async_process_ha_core_config
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from . import MOCK_CONFIG_DATA

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.twilio.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.cloud.async_active_subscription", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_is_logged_in", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_is_connected", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_create_cloudhook",
        return_value="https://hooks.nabu.casa/ABCD",
    ) as fake_create_cloudhook:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "account_sid": "12345678",
                "auth_token": "token",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1
    fake_create_cloudhook.assert_called_once()
    assert result2["data"]["cloudhook"]
    assert result2["description_placeholders"] == {
        "docs_url": "https://www.home-assistant.io/integrations/twilio/",
        "twilio_url": "https://www.twilio.com/docs/glossary/what-is-a-webhook",
        "webhook_url": "https://hooks.nabu.casa/ABCD",
    }


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test a successful import from yaml and update existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"webhook_id": "ABCD", "cloudhook": True}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.twilio.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.cloud.async_active_subscription", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_is_logged_in", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_is_connected", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_create_cloudhook",
        return_value="https://hooks.nabu.casa/ABCD",
    ) as fake_create_cloudhook:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "account_sid": "12345678",
                "auth_token": "token",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"

    assert len(mock_setup_entry.mock_calls) == 1
    fake_create_cloudhook.assert_not_called()

    assert entry.data["account_sid"] == "12345678"
    assert entry.data["auth_token"] == "token"


async def test_options(hass: HomeAssistant) -> None:
    """Test showing webhook url through the options menu."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG_DATA, "webhook_id": "ABCD", "cloudhook": True},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.twilio.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["description_placeholders"] == {
        "docs_url": "https://www.home-assistant.io/integrations/twilio/",
        "twilio_url": "https://www.twilio.com/docs/glossary/what-is-a-webhook",
        "webhook_url": "http://example.local:8123/api/webhook/ABCD",
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_integration_already_configured(hass: HomeAssistant) -> None:
    """Test aborting if the integration is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_with_cloud_sub_not_connected(hass):
    """Test creating a config flow while subscribed."""
    assert await async_setup_component(hass, "cloud", {})

    with patch(
        "homeassistant.components.cloud.async_active_subscription", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_is_logged_in", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_is_connected", return_value=False
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                "account_sid": "12345678",
                "auth_token": "token",
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cloud_not_connected"
