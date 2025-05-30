"""Test pi_hole config flow."""

from homeassistant.components import pi_hole
from homeassistant.components.pi_hole.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_API_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    CONFIG_DATA_DEFAULTS,
    CONFIG_ENTRY_WITH_API_KEY,
    CONFIG_FLOW_API_KEY,
    CONFIG_FLOW_USER,
    NAME,
    ZERO_DATA,
    _create_mocked_hole,
    _patch_config_flow_hole,
    _patch_init_hole,
    _patch_setup_hole,
)

from tests.common import MockConfigEntry


async def test_flow_user_with_api_key_v6(hass: HomeAssistant) -> None:
    """Test user initialized flow with api key needed."""
    mocked_hole = _create_mocked_hole(has_data=False)
    with _patch_config_flow_hole(mocked_hole), _patch_setup_hole() as mock_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
        )
        # we have had no response from the server yet, so we expect an error
        assert result["errors"] == {CONF_API_KEY: "invalid_auth"}

        # now we mock the response from the server
        mocked_hole.data = ZERO_DATA
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_API_KEY,
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == NAME
        assert result["data"] == CONFIG_ENTRY_WITH_API_KEY
        mock_setup.assert_called_once()

        # duplicated server
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_FLOW_USER,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_flow_user_with_api_key_v5(hass: HomeAssistant) -> None:
    """Test user initialized flow with api key needed."""
    mocked_hole = _create_mocked_hole(has_data=False, api_version=5)
    with _patch_config_flow_hole(mocked_hole), _patch_setup_hole() as mock_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
        )
        assert result["errors"] == {CONF_API_KEY: "invalid_auth"}

        mocked_hole.data = ZERO_DATA
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_API_KEY,
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == NAME
        v5_entry = {**CONFIG_ENTRY_WITH_API_KEY}
        v5_entry[CONF_API_VERSION] = 5
        assert result["data"] == v5_entry
        mock_setup.assert_called_once()

        # duplicated server
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_FLOW_USER,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_flow_user_invalid(hass: HomeAssistant) -> None:
    """Test user initialized flow with completely invalid server."""
    mocked_hole = _create_mocked_hole(raise_exception=True)
    with _patch_config_flow_hole(mocked_hole):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG_FLOW_USER
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_user_invalid_v6(hass: HomeAssistant) -> None:
    """Test user initialized flow with invalid server - typically a V6 API and a incorrect app password."""
    mocked_hole = _create_mocked_hole(
        has_data=True, api_version=6, incorrect_app_password=True
    )
    with _patch_config_flow_hole(mocked_hole):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG_FLOW_USER
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {CONF_API_KEY: "invalid_auth"}


async def test_flow_reauth(hass: HomeAssistant) -> None:
    """Test reauth flow."""
    mocked_hole = _create_mocked_hole(has_data=False)
    entry = MockConfigEntry(domain=pi_hole.DOMAIN, data=CONFIG_DATA_DEFAULTS)
    entry.add_to_hass(hass)
    with _patch_init_hole(mocked_hole), _patch_config_flow_hole(mocked_hole):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        flows = hass.config_entries.flow.async_progress()

        assert len(flows) == 1
        assert flows[0]["step_id"] == "reauth_confirm"
        assert flows[0]["context"]["entry_id"] == entry.entry_id

        mocked_hole.data = ZERO_DATA

        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"],
            user_input={CONF_API_KEY: "newkey"},
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert entry.data[CONF_API_KEY] == "newkey"
