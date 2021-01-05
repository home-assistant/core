"""Tests for Barry config flow."""
import pytest

from homeassistant.components.barry.const import DOMAIN

from tests.async_mock import patch

# from tests.common import MockConfigEntry


@pytest.fixture(name="barry_setup", autouse=True)
def barry_setup_fixture():
    """Patch Barry setup entry."""
    with patch("homeassistant.components.barry.async_setup_entry", return_value=True):
        yield


async def test_show_config_form(hass):
    """Test show configuration form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
