"""Test the config flow."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aioruckus.const import (
    ERROR_CONNECT_TEMPORARY,
    ERROR_CONNECT_TIMEOUT,
    ERROR_LOGIN_INCORRECT,
)
from aioruckus.exceptions import AuthenticationError

from homeassistant import config_entries
from homeassistant.components.ruckus_unleashed.const import (
    API_CLIENT_MAC,
    API_SYS_SYSINFO,
    API_SYS_SYSINFO_SERIAL,
    CONF_MAC_FILTER,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import utcnow

from . import (
    CONFIG,
    DEFAULT_SYSTEM_INFO,
    DEFAULT_TITLE,
    TEST_CLIENT,
    RuckusAjaxApiPatchContext,
    init_integration,
    mock_config_entry,
)

from tests.common import async_fire_time_changed


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        RuckusAjaxApiPatchContext(),
        patch(
            "homeassistant.components.ruckus_unleashed.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )
        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == DEFAULT_TITLE
    assert result2["data"] == CONFIG


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with RuckusAjaxApiPatchContext(
        login_mock=AsyncMock(side_effect=AuthenticationError(ERROR_LOGIN_INCORRECT))
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_user_reauth(hass: HomeAssistant) -> None:
    """Test reauth."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert "flow_id" in flows[0]

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with RuckusAjaxApiPatchContext():
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "new_name",
                CONF_PASSWORD: "new_pass",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_form_user_reauth_different_unique_id(hass: HomeAssistant) -> None:
    """Test reauth."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert "flow_id" in flows[0]

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    system_info = deepcopy(DEFAULT_SYSTEM_INFO)
    system_info[API_SYS_SYSINFO][API_SYS_SYSINFO_SERIAL] = "000000000"
    with RuckusAjaxApiPatchContext(system_info=system_info):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "new_name",
                CONF_PASSWORD: "new_pass",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "invalid_host"


async def test_form_user_reauth_invalid_auth(hass: HomeAssistant) -> None:
    """Test reauth."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert "flow_id" in flows[0]

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with RuckusAjaxApiPatchContext(
        login_mock=AsyncMock(side_effect=AuthenticationError(ERROR_LOGIN_INCORRECT))
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "new_name",
                CONF_PASSWORD: "new_pass",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_user_reauth_cannot_connect(hass: HomeAssistant) -> None:
    """Test reauth."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert "flow_id" in flows[0]

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with RuckusAjaxApiPatchContext(
        login_mock=AsyncMock(side_effect=ConnectionError(ERROR_CONNECT_TIMEOUT))
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "new_name",
                CONF_PASSWORD: "new_pass",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_user_reauth_general_exception(hass: HomeAssistant) -> None:
    """Test reauth."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert "flow_id" in flows[0]

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with RuckusAjaxApiPatchContext(login_mock=AsyncMock(side_effect=Exception)):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "new_name",
                CONF_PASSWORD: "new_pass",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with RuckusAjaxApiPatchContext(
        login_mock=AsyncMock(side_effect=ConnectionError(ERROR_CONNECT_TIMEOUT))
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_general_exception(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with RuckusAjaxApiPatchContext(login_mock=AsyncMock(side_effect=Exception)):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_unexpected_response(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with RuckusAjaxApiPatchContext(
        login_mock=AsyncMock(
            side_effect=ConnectionRefusedError(ERROR_CONNECT_TEMPORARY)
        )
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_duplicate_error(hass: HomeAssistant) -> None:
    """Test we handle duplicate error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with RuckusAjaxApiPatchContext():
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

        future = utcnow() + timedelta(minutes=60)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow shows form and accepts selection."""
    entry = await init_integration(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Verify selecting the active client works
    with RuckusAjaxApiPatchContext():
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_MAC_FILTER: [TEST_CLIENT[API_CLIENT_MAC]]},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_MAC_FILTER] == [TEST_CLIENT[API_CLIENT_MAC]]


async def test_options_flow_offline_clients_preserved(hass: HomeAssistant) -> None:
    """Test previously selected but now-offline clients remain selectable."""
    offline_mac = "FF:EE:DD:CC:BB:AA"
    entry = await init_integration(hass)
    hass.config_entries.async_update_entry(
        entry, options={CONF_MAC_FILTER: [offline_mac]}
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    # Verify the offline MAC is still a valid option by submitting it
    with RuckusAjaxApiPatchContext():
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_MAC_FILTER: [offline_mac]},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_MAC_FILTER] == [offline_mac]


async def test_options_flow_removes_deselected_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that deselected devices have their entities removed."""
    entry = await init_integration(hass)

    # Verify entity exists for TEST_CLIENT
    assert entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, TEST_CLIENT[API_CLIENT_MAC]
    )

    # Set a filter that excludes TEST_CLIENT by selecting a different MAC.
    # We add both the active client and a previously-selected offline MAC to
    # the current options so both appear in the multi-select.
    offline_mac = "FF:EE:DD:CC:BB:AA"
    hass.config_entries.async_update_entry(
        entry,
        options={CONF_MAC_FILTER: [TEST_CLIENT[API_CLIENT_MAC], offline_mac]},
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with RuckusAjaxApiPatchContext():
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_MAC_FILTER: [offline_mac]},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY

    # TEST_CLIENT entity should be removed since it's not in the new filter
    assert not entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, TEST_CLIENT[API_CLIENT_MAC]
    )


async def test_options_flow_clear_filter_keeps_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that clearing the filter does not remove entities."""
    entry = await init_integration(hass)

    # Verify entity exists
    assert entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, TEST_CLIENT[API_CLIENT_MAC]
    )

    # Set a filter first
    hass.config_entries.async_update_entry(
        entry,
        options={CONF_MAC_FILTER: [TEST_CLIENT[API_CLIENT_MAC]]},
    )

    # Now clear the filter (empty = track all)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    with RuckusAjaxApiPatchContext():
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_MAC_FILTER: []},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_MAC_FILTER] == []

    # Entity should NOT be removed when going back to track-all
    assert entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, TEST_CLIENT[API_CLIENT_MAC]
    )
