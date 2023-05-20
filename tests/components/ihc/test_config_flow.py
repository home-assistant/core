"""Test the ihc config flow."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.ihc.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.ihc.config_flow.IHCController.is_ihc_controller",
        return_value=True,
    ), patch(
        "homeassistant.components.ihc.config_flow.IHCController.authenticate",
        return_value=True,
    ), patch(
        "homeassistant.components.ihc.config_flow.IHCController.disconnect",
        return_value=None,
    ), patch(
        "homeassistant.components.ihc.config_flow.get_controller_serial",
        return_value="123",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "auto_setup": True,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "IHC Controller"
    assert result2["data"] == {
        "url": "http://1.1.1.1",
        "username": "test-username",
        "password": "test-password",
        "auto_setup": True,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ihc.config_flow.IHCController.is_ihc_controller",
        return_value=True,
    ), patch(
        "homeassistant.components.ihc.config_flow.IHCController.authenticate",
        return_value=False,
    ), patch(
        "homeassistant.components.ihc.config_flow.IHCController.disconnect",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "auto_setup": True,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ihc.config_flow.IHCController.is_ihc_controller",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "auto_setup": True,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_already_setup(hass: HomeAssistant) -> None:
    """Test if controller is already setup."""
    MockConfigEntry(domain=DOMAIN, unique_id="123", data={}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.ihc.config_flow.IHCController.is_ihc_controller",
        return_value=True,
    ), patch(
        "homeassistant.components.ihc.config_flow.IHCController.authenticate",
        return_value=True,
    ), patch(
        "homeassistant.components.ihc.config_flow.IHCController.disconnect",
        return_value=None,
    ), patch(
        "homeassistant.components.ihc.config_flow.get_controller_serial",
        return_value="123",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "auto_setup": True,
            },
        )
        await hass.async_block_till_done()

    assert result2["errors"] == {"base": "already_setup"}


async def test_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown error during commonication with the controller."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.ihc.config_flow.IHCController.is_ihc_controller",
        side_effect=OSError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "auto_setup": True,
            },
        )
        await hass.async_block_till_done()

    assert result2["errors"] == {"base": "unknown"}


def _get_schema_default(schema, key_name):
    """Iterate schema to find a key."""
    for schema_key in schema:
        if schema_key == key_name:
            return schema_key.default()
    raise KeyError(f"{key_name} not found in schema")
