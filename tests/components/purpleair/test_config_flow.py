"""Define tests for the PurpleAir config flow."""

from unittest.mock import AsyncMock, patch

from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
import pytest

from homeassistant.components.purpleair.const import (
    CONF_ALREADY_CONFIGURED,
    CONF_INVALID_API_KEY,
    CONF_REAUTH_CONFIRM,
    CONF_REAUTH_SUCCESSFUL,
    CONF_RECONFIGURE,
    CONF_RECONFIGURE_SUCCESSFUL,
    CONF_SETTINGS,
    CONF_UNKNOWN,
    DOMAIN,
    TITLE,
)
from homeassistant.const import CONF_API_KEY, CONF_BASE, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    CONF_DATA,
    CONF_ERRORS,
    CONF_FLOW_ID,
    CONF_OPTIONS,
    CONF_REASON,
    CONF_SOURCE,
    CONF_SOURCE_USER,
    CONF_STEP_ID,
    CONF_TITLE,
    CONF_TYPE,
    TEST_API_KEY,
    TEST_NEW_API_KEY,
)


async def test_user_init(hass: HomeAssistant, mock_aiopurpleair, api) -> None:
    """Test user initialization flow."""

    # User init
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: CONF_SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_API_KEY

    # API key
    with patch.object(api, "async_check_api_key"):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_API_KEY}
        )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_DATA] == {
        CONF_API_KEY: TEST_API_KEY,
    }
    assert result[CONF_OPTIONS] == {
        CONF_SHOW_ON_MAP: False,
    }
    assert result[CONF_TITLE] == TITLE

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    # Add second entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: CONF_SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_API_KEY

    # Different API key for second entry
    with patch.object(api, "async_check_api_key"):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_NEW_API_KEY}
        )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_DATA] == {
        CONF_API_KEY: TEST_NEW_API_KEY,
    }
    assert result[CONF_TITLE] == f"{TITLE} (1)"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2


async def test_reconfigure(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    mock_aiopurpleair,
    api,
) -> None:
    """Test reconfigure."""

    # Reconfigure
    result = await config_entry.start_reconfigure_flow(hass)
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_RECONFIGURE

    # Bad API key
    with patch.object(
        api, "async_check_api_key", AsyncMock(side_effect=InvalidApiKeyError)
    ):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_NEW_API_KEY}
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_ERRORS] == {CONF_API_KEY: CONF_INVALID_API_KEY}

    # API key
    with patch.object(api, "async_check_api_key"):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_NEW_API_KEY}
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.ABORT
    assert result[CONF_REASON] == CONF_RECONFIGURE_SUCCESSFUL

    assert config_entry.data[CONF_API_KEY] == TEST_NEW_API_KEY


async def test_reauth(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    mock_aiopurpleair,
    api,
) -> None:
    """Test reauth."""

    # Reauth
    result = await config_entry.start_reauth_flow(hass)
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_REAUTH_CONFIRM

    # Bad API key
    with patch.object(
        api, "async_check_api_key", AsyncMock(side_effect=InvalidApiKeyError)
    ):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_NEW_API_KEY}
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_ERRORS] == {CONF_API_KEY: CONF_INVALID_API_KEY}

    # API key
    with patch.object(api, "async_check_api_key"):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_NEW_API_KEY}
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.ABORT
    assert result[CONF_REASON] == CONF_REAUTH_SUCCESSFUL

    assert config_entry.data[CONF_API_KEY] == TEST_NEW_API_KEY


async def test_duplicate_api_key(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    mock_aiopurpleair,
    api,
) -> None:
    """Test duplicate API key flow."""

    # User init
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: CONF_SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_API_KEY

    # API key
    with patch.object(api, "async_check_api_key"):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_API_KEY}
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_ERRORS] == {CONF_API_KEY: CONF_ALREADY_CONFIGURED}

    hass.config_entries.flow.async_abort(result[CONF_FLOW_ID])
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("check_api_key_mock", "check_api_key_errors"),
    [
        (AsyncMock(side_effect=Exception), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=PurpleAirError), {CONF_BASE: CONF_UNKNOWN}),
        (
            AsyncMock(side_effect=InvalidApiKeyError),
            {CONF_API_KEY: CONF_INVALID_API_KEY},
        ),
        (AsyncMock(return_value=None), {CONF_BASE: CONF_UNKNOWN}),
    ],
)
async def test_user_init_errors(
    hass: HomeAssistant,
    mock_aiopurpleair,
    api,
    check_api_key_mock,
    check_api_key_errors,
) -> None:
    """Test user initialization flow."""

    # User init
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: CONF_SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_API_KEY

    # API key
    with patch.object(api, "async_check_api_key", check_api_key_mock):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_API_KEY}
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_ERRORS] == check_api_key_errors

    hass.config_entries.flow.async_abort(result[CONF_FLOW_ID])
    await hass.async_block_till_done()


async def test_options_settings(
    hass: HomeAssistant, config_entry, setup_config_entry
) -> None:
    """Test options setting flow."""

    # Options init
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_SETTINGS

    # Settings
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_SHOW_ON_MAP: True}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_DATA] == {
        CONF_SHOW_ON_MAP: True,
    }
