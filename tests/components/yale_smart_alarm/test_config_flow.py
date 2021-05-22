"""Test the Yale Smart Living config flow."""
from __future__ import annotations

from unittest.mock import patch

from yalesmartalarmclient.client import AuthenticationError

from homeassistant import config_entries, setup
from homeassistant.components.yale_smart_alarm.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
        return_value=True,
    ), patch(
        "homeassistant.components.yale_smart_alarm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "name": "Yale Smart Alarm",
                "area_id": "1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
        "name": "Yale Smart Alarm",
        "area_id": "1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
        side_effect=AuthenticationError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "name": "Yale Smart Alarm",
                "area_id": "1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_import_flow_success(hass):
    """Test a successful import of yaml."""
    with patch(
        "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
        return_value=True,
    ), patch(
        "homeassistant.components.yale_smart_alarm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "username": "test-username",
                "password": "test-password",
                "name": "Yale Smart Alarm",
                "area_id": "1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
        "name": "Yale Smart Alarm",
        "area_id": "1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_success_missing_requirement(hass):
    """Test a successful import of yaml where new requirements missing."""
    with patch(
        "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
        return_value=True,
    ), patch(
        "homeassistant.components.yale_smart_alarm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "test-username"
    assert result3["data"] == {
        "username": "test-username",
        "password": "test-password",
        "name": "Yale Smart Alarm",
        "area_id": "1",
    }
    assert len(mock_setup_entry.mock_calls) == 1
