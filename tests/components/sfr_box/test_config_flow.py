"""Test the SFR Box config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from sfrbox_api.exceptions import SFRBoxAuthenticationError, SFRBoxError
from sfrbox_api.models import SystemInfo

from homeassistant import config_entries
from homeassistant.components.sfr_box.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import async_load_json_object_fixture

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_config_flow_skip_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow (no authentication)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.system_get_info",
        return_value=SystemInfo(
            **(
                await async_load_json_object_fixture(
                    hass, "system_getInfo.json", DOMAIN
                )
            )
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.0.1",
            },
        )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "choose_auth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "skip_auth"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SFR Box"
    assert result["data"] == {CONF_HOST: "192.168.0.1"}
    assert result["context"]["unique_id"] == "e4:5d:51:00:11:22"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_skip_auth_failure(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow (no authentication) with failure and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.system_get_info",
        side_effect=SFRBoxError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.0.1",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.system_get_info",
        return_value=SystemInfo(
            **(
                await async_load_json_object_fixture(
                    hass, "system_getInfo.json", DOMAIN
                )
            )
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.0.1",
            },
        )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "choose_auth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "skip_auth"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SFR Box"
    assert result["data"] == {CONF_HOST: "192.168.0.1"}
    assert result["context"]["unique_id"] == "e4:5d:51:00:11:22"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_with_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow (with authentication)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.system_get_info",
        return_value=SystemInfo(
            **(
                await async_load_json_object_fixture(
                    hass, "system_getInfo.json", DOMAIN
                )
            )
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.0.1",
            },
        )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "choose_auth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "auth"},
    )

    with patch("homeassistant.components.sfr_box.config_flow.SFRBox.authenticate"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "valid",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SFR Box"
    assert result["data"] == {
        CONF_HOST: "192.168.0.1",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "valid",
    }
    assert result["context"]["unique_id"] == "e4:5d:51:00:11:22"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_with_auth_failure(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow (with authentication) with failure and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.system_get_info",
        return_value=SystemInfo(
            **(
                await async_load_json_object_fixture(
                    hass, "system_getInfo.json", DOMAIN
                )
            )
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.0.1",
            },
        )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "choose_auth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "auth"},
    )

    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.authenticate",
        side_effect=SFRBoxAuthenticationError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "invalid",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch("homeassistant.components.sfr_box.config_flow.SFRBox.authenticate"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "valid",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SFR Box"
    assert result["data"] == {
        CONF_HOST: "192.168.0.1",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "valid",
    }
    assert result["context"]["unique_id"] == "e4:5d:51:00:11:22"

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("config_entry")
async def test_config_flow_duplicate_host(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test abort if unique_id configured."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    system_info = SystemInfo(
        **(await async_load_json_object_fixture(hass, "system_getInfo.json", DOMAIN))
    )
    # Ensure mac doesn't match existing mock entry
    system_info.mac_addr = "aa:bb:cc:dd:ee:ff"
    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.system_get_info",
        return_value=system_info,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.0.1",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 0


@pytest.mark.usefixtures("config_entry")
async def test_config_flow_duplicate_mac(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test abort if unique_id configured."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    system_info = SystemInfo(
        **(await async_load_json_object_fixture(hass, "system_getInfo.json", DOMAIN))
    )
    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.system_get_info",
        return_value=system_info,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.0.2",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 0


async def test_reauth(hass: HomeAssistant, config_entry_with_auth: ConfigEntry) -> None:
    """Test the start of the config flow."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await config_entry_with_auth.start_reauth_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}

    # Failed credentials
    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.authenticate",
        side_effect=SFRBoxAuthenticationError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "invalid",
            },
        )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "invalid_auth"}

    # Valid credentials
    with patch("homeassistant.components.sfr_box.config_flow.SFRBox.authenticate"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "new_password",
            },
        )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"


async def test_reconfigure_host(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Test reconfigure host on a simple (no-auth) entry."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await config_entry.start_reconfigure_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {}

    assert config_entry.data[CONF_HOST] == "192.168.0.1"
    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.system_get_info",
        return_value=SystemInfo(
            **(
                await async_load_json_object_fixture(
                    hass, "system_getInfo.json", DOMAIN
                )
            )
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.0.100",
            },
        )

    assert result.get("type") is FlowResultType.MENU
    assert result.get("step_id") == "choose_auth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "skip_auth"},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"
    assert config_entry.data == {CONF_HOST: "192.168.0.100"}


async def test_reconfigure_add_auth(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test reconfigure able to add authentication on a simple (no-auth) entry."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await config_entry.start_reconfigure_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {}

    assert CONF_USERNAME not in config_entry.data
    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.system_get_info",
        return_value=SystemInfo(
            **(
                await async_load_json_object_fixture(
                    hass, "system_getInfo.json", DOMAIN
                )
            )
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.0.1",
            },
        )

    assert result.get("type") is FlowResultType.MENU
    assert result.get("step_id") == "choose_auth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "auth"},
    )

    with patch("homeassistant.components.sfr_box.config_flow.SFRBox.authenticate"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "valid",
            },
        )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"
    assert config_entry.data == {
        CONF_HOST: "192.168.0.1",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "valid",
    }


async def test_reconfigure_clear_auth(
    hass: HomeAssistant, config_entry_with_auth: ConfigEntry
) -> None:
    """Test reconfigure clears authentication on an entry with auth."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await config_entry_with_auth.start_reconfigure_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {}

    assert config_entry_with_auth.data[CONF_USERNAME] == "admin"
    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.system_get_info",
        return_value=SystemInfo(
            **(
                await async_load_json_object_fixture(
                    hass, "system_getInfo.json", DOMAIN
                )
                | {"mac_addr": "e4:5d:51:00:11:23"}
            )
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.0.1",
            },
        )

    assert result.get("type") is FlowResultType.MENU
    assert result.get("step_id") == "choose_auth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "skip_auth"},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"
    assert CONF_USERNAME not in config_entry_with_auth.data


async def test_reconfigure_mismatch(
    hass: HomeAssistant, config_entry_with_auth: ConfigEntry
) -> None:
    """Test reconfigure fails if the unique ID (=MAC) does not match."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await config_entry_with_auth.start_reconfigure_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {}

    assert config_entry_with_auth.data[CONF_USERNAME] == "admin"
    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.system_get_info",
        return_value=SystemInfo(
            **(
                await async_load_json_object_fixture(
                    hass, "system_getInfo.json", DOMAIN
                )
            )
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.0.1",
            },
        )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "unique_id_mismatch"
