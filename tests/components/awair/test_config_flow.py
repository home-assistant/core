"""Define tests for the Awair config flow."""

from typing import Any
from unittest.mock import Mock, patch

from aiohttp.client_exceptions import ClientConnectorError
from python_awair.exceptions import AuthError, AwairError

from homeassistant.components.awair.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    CLOUD_CONFIG,
    CLOUD_UNIQUE_ID,
    LOCAL_CONFIG,
    LOCAL_UNIQUE_ID,
    ZEROCONF_DISCOVERY,
)

from tests.common import MockConfigEntry


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"


async def test_invalid_access_token(hass: HomeAssistant) -> None:
    """Test that errors are shown when the access token is invalid."""

    with patch("python_awair.AwairClient.query", side_effect=AuthError()):
        menu_step = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CLOUD_CONFIG
        )

        form_step = await hass.config_entries.flow.async_configure(
            menu_step["flow_id"],
            {"next_step_id": "cloud"},
        )

        result = await hass.config_entries.flow.async_configure(
            form_step["flow_id"],
            CLOUD_CONFIG,
        )

        assert result["errors"] == {CONF_ACCESS_TOKEN: "invalid_access_token"}


async def test_unexpected_api_error(hass: HomeAssistant) -> None:
    """Test that we abort on generic errors."""

    with patch("python_awair.AwairClient.query", side_effect=AwairError()):
        menu_step = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CLOUD_CONFIG
        )

        form_step = await hass.config_entries.flow.async_configure(
            menu_step["flow_id"],
            {"next_step_id": "cloud"},
        )

        result = await hass.config_entries.flow.async_configure(
            form_step["flow_id"],
            CLOUD_CONFIG,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "unknown"


async def test_duplicate_error(hass: HomeAssistant, user, cloud_devices) -> None:
    """Test that errors are shown when adding a duplicate config."""

    with patch(
        "python_awair.AwairClient.query",
        side_effect=[user, cloud_devices],
    ):
        MockConfigEntry(
            domain=DOMAIN, unique_id=CLOUD_UNIQUE_ID, data=CLOUD_CONFIG
        ).add_to_hass(hass)

        menu_step = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CLOUD_CONFIG
        )

        form_step = await hass.config_entries.flow.async_configure(
            menu_step["flow_id"],
            {"next_step_id": "cloud"},
        )

        result = await hass.config_entries.flow.async_configure(
            form_step["flow_id"],
            CLOUD_CONFIG,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured_account"


async def test_no_devices_error(hass: HomeAssistant, user, no_devices) -> None:
    """Test that errors are shown when the API returns no devices."""

    with patch("python_awair.AwairClient.query", side_effect=[user, no_devices]):
        menu_step = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CLOUD_CONFIG
        )

        form_step = await hass.config_entries.flow.async_configure(
            menu_step["flow_id"],
            {"next_step_id": "cloud"},
        )

        result = await hass.config_entries.flow.async_configure(
            form_step["flow_id"],
            CLOUD_CONFIG,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"


async def test_reauth(hass: HomeAssistant, user, cloud_devices) -> None:
    """Test reauth flow."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        unique_id=CLOUD_UNIQUE_ID,
        data={**CLOUD_CONFIG, CONF_ACCESS_TOKEN: "blah"},
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "unique_id": CLOUD_UNIQUE_ID},
        data={**CLOUD_CONFIG, CONF_ACCESS_TOKEN: "blah"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    with patch("python_awair.AwairClient.query", side_effect=AuthError()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CLOUD_CONFIG,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {CONF_ACCESS_TOKEN: "invalid_access_token"}

    with (
        patch(
            "python_awair.AwairClient.query",
            side_effect=[user, cloud_devices],
        ),
        patch("homeassistant.components.awair.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CLOUD_CONFIG,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"


async def test_reauth_error(hass: HomeAssistant) -> None:
    """Test reauth flow."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        unique_id=CLOUD_UNIQUE_ID,
        data={**CLOUD_CONFIG, CONF_ACCESS_TOKEN: "blah"},
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "unique_id": CLOUD_UNIQUE_ID},
        data={**CLOUD_CONFIG, CONF_ACCESS_TOKEN: "blah"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    with patch("python_awair.AwairClient.query", side_effect=AwairError()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CLOUD_CONFIG,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "unknown"


async def test_create_cloud_entry(hass: HomeAssistant, user, cloud_devices) -> None:
    """Test overall flow when using cloud api."""

    with (
        patch(
            "python_awair.AwairClient.query",
            side_effect=[user, cloud_devices],
        ),
        patch(
            "homeassistant.components.awair.async_setup_entry",
            return_value=True,
        ),
    ):
        menu_step = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CLOUD_CONFIG
        )

        form_step = await hass.config_entries.flow.async_configure(
            menu_step["flow_id"],
            {"next_step_id": "cloud"},
        )

        result = await hass.config_entries.flow.async_configure(
            form_step["flow_id"],
            CLOUD_CONFIG,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "foo@bar.com"
        assert result["data"][CONF_ACCESS_TOKEN] == CLOUD_CONFIG[CONF_ACCESS_TOKEN]
        assert result["result"].unique_id == CLOUD_UNIQUE_ID


async def test_create_local_entry(hass: HomeAssistant, local_devices) -> None:
    """Test overall flow when using local API."""

    with (
        patch("python_awair.AwairClient.query", side_effect=[local_devices]),
        patch(
            "homeassistant.components.awair.async_setup_entry",
            return_value=True,
        ),
    ):
        menu_step = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=LOCAL_CONFIG
        )

        form_step = await hass.config_entries.flow.async_configure(
            menu_step["flow_id"],
            {"next_step_id": "local"},
        )

        # We're being shown the local instructions
        form_step = await hass.config_entries.flow.async_configure(
            form_step["flow_id"],
            {},
        )

        result = await hass.config_entries.flow.async_configure(
            form_step["flow_id"],
            LOCAL_CONFIG,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Awair Element (24947)"
        assert result["data"][CONF_HOST] == LOCAL_CONFIG[CONF_HOST]
        assert result["result"].unique_id == LOCAL_UNIQUE_ID


async def test_create_local_entry_from_discovery(
    hass: HomeAssistant, local_devices
) -> None:
    """Test local API when device discovered after instructions shown."""

    menu_step = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=LOCAL_CONFIG
    )

    form_step = await hass.config_entries.flow.async_configure(
        menu_step["flow_id"],
        {"next_step_id": "local"},
    )

    # Create discovered entry in progress
    with patch("python_awair.AwairClient.query", side_effect=[local_devices]):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            data=Mock(host=LOCAL_CONFIG[CONF_HOST]),
            context={"source": SOURCE_ZEROCONF},
        )

    # We're being shown the local instructions
    form_step = await hass.config_entries.flow.async_configure(
        form_step["flow_id"],
        {},
    )

    with (
        patch("python_awair.AwairClient.query", side_effect=[local_devices]),
        patch(
            "homeassistant.components.awair.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            form_step["flow_id"],
            {"device": LOCAL_CONFIG[CONF_HOST]},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Awair Element (24947)"
    assert result["data"][CONF_HOST] == LOCAL_CONFIG[CONF_HOST]
    assert result["result"].unique_id == LOCAL_UNIQUE_ID


async def test_create_local_entry_awair_error(hass: HomeAssistant) -> None:
    """Test overall flow when using local API and device is returns error."""

    with patch(
        "python_awair.AwairClient.query",
        side_effect=AwairError(),
    ):
        menu_step = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=LOCAL_CONFIG
        )

        form_step = await hass.config_entries.flow.async_configure(
            menu_step["flow_id"],
            {"next_step_id": "local"},
        )

        # We're being shown the local instructions
        form_step = await hass.config_entries.flow.async_configure(
            form_step["flow_id"],
            {},
        )

        result = await hass.config_entries.flow.async_configure(
            form_step["flow_id"],
            LOCAL_CONFIG,
        )

        # User is returned to form to try again
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "local_pick"


async def test_create_zeroconf_entry(hass: HomeAssistant, local_devices) -> None:
    """Test overall flow when using discovery."""

    with (
        patch("python_awair.AwairClient.query", side_effect=[local_devices]),
        patch(
            "homeassistant.components.awair.async_setup_entry",
            return_value=True,
        ),
    ):
        confirm_step = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
        )

        result = await hass.config_entries.flow.async_configure(
            confirm_step["flow_id"],
            {},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Awair Element (24947)"
        assert result["data"][CONF_HOST] == ZEROCONF_DISCOVERY.host
        assert result["result"].unique_id == LOCAL_UNIQUE_ID


async def test_unsuccessful_create_zeroconf_entry(hass: HomeAssistant) -> None:
    """Test overall flow when using discovery and device is unreachable."""

    with patch(
        "python_awair.AwairClient.query",
        side_effect=ClientConnectorError(Mock(), OSError()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
        )

        assert result["type"] is FlowResultType.ABORT


async def test_zeroconf_discovery_update_configuration(
    hass: HomeAssistant, local_devices: Any
) -> None:
    """Test updating an existing Awair config entry with discovery info."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
        unique_id=LOCAL_UNIQUE_ID,
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.awair.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch("python_awair.AwairClient.query", side_effect=[local_devices]),
        patch(
            "homeassistant.components.awair.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=ZEROCONF_DISCOVERY,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured_device"

        assert config_entry.data[CONF_HOST] == ZEROCONF_DISCOVERY.host
        assert mock_setup_entry.call_count == 0


async def test_zeroconf_during_onboarding(
    hass: HomeAssistant, local_devices: Any
) -> None:
    """Test the zeroconf creates an entry during onboarding."""
    with (
        patch(
            "homeassistant.components.awair.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch("python_awair.AwairClient.query", side_effect=[local_devices]),
        patch(
            "homeassistant.components.onboarding.async_is_onboarded",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
        )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Awair Element (24947)"
    assert "data" in result
    assert result["data"][CONF_HOST] == ZEROCONF_DISCOVERY.host
    assert "result" in result
    assert result["result"].unique_id == LOCAL_UNIQUE_ID
    assert len(mock_setup_entry.mock_calls) == 1
