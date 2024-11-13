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
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
        ),
        patch(
            "homeassistant.components.yale_smart_alarm.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
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

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
        "name": "Yale Smart Alarm",
        "area_id": "1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("sideeffect", "p_error"),
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

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": p_error}

    with (
        patch(
            "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
        ),
        patch(
            "homeassistant.components.yale_smart_alarm.async_setup_entry",
            return_value=True,
        ),
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

    assert result2["type"] is FlowResultType.CREATE_ENTRY
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
        version=2,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
        ) as mock_yale,
        patch(
            "homeassistant.components.yale_smart_alarm.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "password": "new-test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
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
    ("sideeffect", "p_error"),
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
        version=2,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
        side_effect=sideeffect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "password": "wrong-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "reauth_confirm"
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": p_error}

    with (
        patch(
            "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
            return_value="",
        ),
        patch(
            "homeassistant.components.yale_smart_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "password": "new-test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == {
        "username": "test-username",
        "password": "new-test-password",
        "name": "Yale Smart Alarm",
        "area_id": "1",
    }


async def test_reconfigure(hass: HomeAssistant) -> None:
    """Test reconfigure config flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={
            "username": "test-username",
            "password": "test-password",
            "name": "Yale Smart Alarm",
            "area_id": "1",
        },
        version=2,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with (
        patch(
            "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
            return_value="",
        ),
        patch(
            "homeassistant.components.yale_smart_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "new-test-password",
                "area_id": "2",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data == {
        "username": "test-username",
        "password": "new-test-password",
        "name": "Yale Smart Alarm",
        "area_id": "2",
    }


async def test_reconfigure_username_exist(hass: HomeAssistant) -> None:
    """Test reconfigure config flow abort other username already exist."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={
            "username": "test-username",
            "password": "test-password",
            "name": "Yale Smart Alarm",
            "area_id": "1",
        },
        version=2,
    )
    entry.add_to_hass(hass)
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        unique_id="other-username",
        data={
            "username": "other-username",
            "password": "test-password",
            "name": "Yale Smart Alarm 2",
            "area_id": "1",
        },
        version=2,
    )
    entry2.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with (
        patch(
            "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
            return_value="",
        ),
        patch(
            "homeassistant.components.yale_smart_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "other-username",
                "password": "test-password",
                "area_id": "1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unique_id_exists"}

    with (
        patch(
            "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
            return_value="",
        ),
        patch(
            "homeassistant.components.yale_smart_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "other-new-username",
                "password": "test-password",
                "area_id": "1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        "username": "other-new-username",
        "name": "Yale Smart Alarm",
        "password": "test-password",
        "area_id": "1",
    }


@pytest.mark.parametrize(
    ("sideeffect", "p_error"),
    [
        (AuthenticationError, "invalid_auth"),
        (ConnectionError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (UnknownError, "cannot_connect"),
    ],
)
async def test_reconfigure_flow_error(
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
        version=2,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
        side_effect=sideeffect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "update-password",
                "area_id": "1",
            },
        )
        await hass.async_block_till_done()

    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": p_error}

    with (
        patch(
            "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
            return_value="",
        ),
        patch(
            "homeassistant.components.yale_smart_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "new-test-password",
                "area_id": "1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        "username": "test-username",
        "name": "Yale Smart Alarm",
        "password": "new-test-password",
        "area_id": "1",
    }


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options config flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={
            "username": "test-username",
            "password": "test-password",
            "name": "Yale Smart Alarm",
            "area_id": "1",
        },
        version=2,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.yale_smart_alarm.config_flow.YaleSmartAlarmClient",
            return_value=True,
        ),
        patch(
            "homeassistant.components.yale_smart_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"lock_code_digits": 6},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"lock_code_digits": 6}
