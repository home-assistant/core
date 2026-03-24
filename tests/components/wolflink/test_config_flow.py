"""Test the Wolf SmartSet Service config flow."""

from unittest.mock import patch

from httpcore import ConnectError
from wolf_comm.models import Device
from wolf_comm.token_auth import InvalidAuth

from homeassistant import config_entries
from homeassistant.components.wolflink.const import CONF_DEVICES, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import CONFIG

from tests.common import MockConfigEntry

INPUT_CONFIG = {
    CONF_USERNAME: CONFIG[CONF_USERNAME],
    CONF_PASSWORD: CONFIG[CONF_PASSWORD],
}

MOCK_DEVICE = Device(1234, 5678, "test-device")


async def test_show_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test entry creation after successful authentication and device selection."""
    with (
        patch(
            "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
            return_value=[MOCK_DEVICE],
        ),
        patch("homeassistant.components.wolflink.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "devices"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICES: ["1234"]},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == CONFIG[CONF_USERNAME]
    assert result2["data"] == {
        CONF_USERNAME: CONFIG[CONF_USERNAME],
        CONF_PASSWORD: CONFIG[CONF_PASSWORD],
    }
    assert result2["options"] == {
        CONF_DEVICES: ["1234"],
    }


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        side_effect=ConnectError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass: HomeAssistant) -> None:
    """Test we handle unexpected exceptions."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_already_configured_error(hass: HomeAssistant) -> None:
    """Test already configured while creating entry."""
    with (
        patch(
            "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
            return_value=[MOCK_DEVICE],
        ),
        patch("homeassistant.components.wolflink.async_setup_entry", return_value=True),
    ):
        MockConfigEntry(
            domain=DOMAIN,
            unique_id=CONFIG[CONF_USERNAME].lower(),
            data=CONFIG,
        ).add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_init(
    hass: HomeAssistant,
    mock_wolflink,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow shows current device selections."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_save(
    hass: HomeAssistant,
    mock_wolflink,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow saves updated device selection."""
    mock_wolflink.fetch_system_list.return_value = [
        Device(1234, 5678, "test-device"),
        Device(9999, 5678, "other-device"),
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_DEVICES: ["1234", "9999"]},
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_DEVICES] == ["1234", "9999"]


async def test_options_flow_cannot_connect(
    hass: HomeAssistant,
    mock_wolflink,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow handles connection error when fetching device list."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Simulate connection failure only during the options flow fetch
    mock_wolflink.fetch_system_list.side_effect = ConnectError

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow_success(hass: HomeAssistant) -> None:
    """Test reauth flow succeeds with valid credentials for the same account."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=CONFIG[CONF_USERNAME].lower(),
        data=CONFIG,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        return_value=[MOCK_DEVICE],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: CONFIG[CONF_USERNAME],
                CONF_PASSWORD: "new-password",
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-password"


async def test_reauth_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test reauth flow shows error on invalid credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=CONFIG[CONF_USERNAME].lower(),
        data=CONFIG,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: CONFIG[CONF_USERNAME],
                CONF_PASSWORD: "wrong-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_wrong_account(hass: HomeAssistant) -> None:
    """Test reauth flow shows error when credentials belong to a different account."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=CONFIG[CONF_USERNAME].lower(),
        data=CONFIG,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        return_value=[MOCK_DEVICE],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "different-username",
                CONF_PASSWORD: CONFIG[CONF_PASSWORD],
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "wrong_account"}
