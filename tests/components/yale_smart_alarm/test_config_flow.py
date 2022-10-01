"""Test the Yale Smart Living config flow."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from yalesmartalarmclient.exceptions import AuthenticationError, UnknownError

from homeassistant import config_entries
from homeassistant.components.yale_smart_alarm.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
    ), patch(
        "homeassistant.components.yale_smart_alarm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "area_id": "1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
        "name": "Yale Smart Alarm",
        "area_id": "1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "sideeffect,p_error",
    [
        (AuthenticationError, "invalid_auth"),
        (ConnectionError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (UnknownError, "cannot_connect"),
    ],
)
async def test_form_invalid_auth(
    hass: HomeAssistant, sideeffect: Exception, p_error: str
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
        side_effect=sideeffect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "area_id": "1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": p_error}

    with patch(
        "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
    ), patch(
        "homeassistant.components.yale_smart_alarm.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "area_id": "1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
        "name": "Yale Smart Alarm",
        "area_id": "1",
    }


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={
            "username": "test-username",
            "password": "test-password",
            "name": "Yale Smart Alarm",
            "area_id": "1",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
    ) as mock_yale, patch(
        "homeassistant.components.yale_smart_alarm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "new-test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == {
        "username": "test-username",
        "password": "new-test-password",
        "name": "Yale Smart Alarm",
        "area_id": "1",
    }

    assert len(mock_yale.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "sideeffect,p_error",
    [
        (AuthenticationError, "invalid_auth"),
        (ConnectionError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (UnknownError, "cannot_connect"),
    ],
)
async def test_reauth_flow_error(
    hass: HomeAssistant, sideeffect: Exception, p_error: str
) -> None:
    """Test a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={
            "username": "test-username",
            "password": "test-password",
            "name": "Yale Smart Alarm",
            "area_id": "1",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    with patch(
        "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
        side_effect=sideeffect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "wrong-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "reauth_confirm"
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": p_error}

    with patch(
        "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
        return_value="",
    ), patch(
        "homeassistant.components.yale_smart_alarm.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "new-test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == {
        "username": "test-username",
        "password": "new-test-password",
        "name": "Yale Smart Alarm",
        "area_id": "1",
    }


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options config flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.yale_smart_alarm.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"code": "123456", "lock_code_digits": 6},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {"code": "123456", "lock_code_digits": 6}


async def test_options_flow_format_mismatch(hass: HomeAssistant) -> None:
    """Test options config flow with a code format mismatch error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.yale_smart_alarm.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"code": "123", "lock_code_digits": 6},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": "code_format_mismatch"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"code": "123456", "lock_code_digits": 6},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {"code": "123456", "lock_code_digits": 6}
