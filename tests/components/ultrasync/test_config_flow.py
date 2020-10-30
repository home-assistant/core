"""Test the UltraSync config flow."""

from homeassistant.components.ultrasync.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.setup import async_setup_component

from tests.async_mock import MagicMock, patch

from . import (
    ENTRY_CONFIG,
    USER_INPUT,
    _patch_async_setup,
    _patch_async_setup_entry,
)

from tests.common import MockConfigEntry


async def test_user_form(hass, ultrasync_api):
    """Test we get the user initiated form."""
    await async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with _patch_async_setup() as mock_setup, _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "127.0.0.2"
    assert result["data"] == USER_INPUT

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("ultrasync.UltraSync") as mock_api:
        instance = MagicMock()
        instance.login = MagicMock(return_value=False)
        mock_api.return_value = instance

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_form_unexpected_exception(hass, ultrasync_api):
    """Test we handle unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("ultrasync.UltraSync") as mock_api:
        instance = MagicMock()
        instance.login = MagicMock(side_effect=Exception())
        mock_api.return_value = instance

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"


async def test_user_form_single_instance_allowed(hass, ultrasync_api):
    """Test that configuring more than one instance is rejected."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow(hass, ultrasync_api):
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_CONFIG,
        options={CONF_SCAN_INTERVAL: 5},
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.ultrasync.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.options[CONF_SCAN_INTERVAL] == 5

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    with _patch_async_setup(), _patch_async_setup_entry():
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_SCAN_INTERVAL: 15},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_SCAN_INTERVAL] == 15
