"""Test the Litter-Robot config flow."""
from unittest.mock import patch

from pylitterbot.exceptions import LitterRobotException, LitterRobotLoginException

from homeassistant import config_entries, setup
from homeassistant.components import litterrobot

from .common import CONF_USERNAME, CONFIG, DOMAIN

from tests.common import MockConfigEntry


async def test_form(hass, mock_account):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.litterrobot.hub.Account",
        return_value=mock_account,
    ), patch(
        "homeassistant.components.litterrobot.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG[DOMAIN]
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == CONFIG[DOMAIN][CONF_USERNAME]
    assert result2["data"] == CONFIG[DOMAIN]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(hass):
    """Test we handle already configured."""
    MockConfigEntry(
        domain=litterrobot.DOMAIN,
        data=CONFIG[litterrobot.DOMAIN],
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=CONFIG[litterrobot.DOMAIN],
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pylitterbot.Account.connect",
        side_effect=LitterRobotLoginException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG[DOMAIN]
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pylitterbot.Account.connect",
        side_effect=LitterRobotException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG[DOMAIN]
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass):
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pylitterbot.Account.connect",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG[DOMAIN]
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
