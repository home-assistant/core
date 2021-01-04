"""Test the roon config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.roon.const import DOMAIN


class RoonHubMock:
    """Class to mock the Roon API for testing."""

    def __init__(self, token, servers):
        """Initialize."""
        self._token = token
        self._servers = servers

    async def discover(self):
        """Return discovered roon servers."""
        return self._servers

    async def authenticate(self, host, servers):
        """Authenticate against roon."""
        return (self._token, "core_id")


class RoonHubMockException(RoonHubMock):
    """Class to mock the Roon API for testing that throws an unexpected exception."""

    async def authenticate(self, hass, host, servers):
        """Throw exception when authenticating."""
        raise Exception


async def test_successful_discovery_and_auth(hass):
    """Test when discovery and auth both work ok."""
    with patch(
        "homeassistant.components.roon.config_flow.RoonHub",
        return_value=RoonHubMock("good_token", ["2.2.2.2"]),
    ), patch("homeassistant.components.roon.async_setup", return_value=True), patch(
        "homeassistant.components.roon.async_setup_entry",
        return_value=True,
    ):

        await setup.async_setup_component(hass, "persistent_notification", {})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

        # Should go straight to link if server was discovered
        assert result["type"] == "form"
        assert result["step_id"] == "link"
        assert result["errors"] == {}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result2["title"] == "Roon Labs Music Player"
    assert result2["data"] == {
        "host": None,
        "api_key": "good_token",
        "roon_server_id": "core_id",
    }


async def test_unsuccessful_discovery_user_form_and_auth(hass):
    """Test unsuccessful discover, user adding the host via the form and then successful auth."""
    with patch(
        "homeassistant.components.roon.config_flow.RoonHub",
        return_value=RoonHubMock("good_token", []),
    ), patch("homeassistant.components.roon.async_setup", return_value=True), patch(
        "homeassistant.components.roon.async_setup_entry",
        return_value=True,
    ):

        await setup.async_setup_component(hass, "persistent_notification", {})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

        # Should show the form if server was not discovered
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.1.1.1"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result2["title"] == "Roon Labs Music Player"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "api_key": "good_token",
        "roon_server_id": "core_id",
    }


async def test_successful_discovery_no_auth(hass):
    """Test successful discover, but failed auth."""
    with patch(
        "homeassistant.components.roon.config_flow.RoonHub",
        return_value=RoonHubMock(None, ["2.2.2.2"]),
    ), patch("homeassistant.components.roon.async_setup", return_value=True), patch(
        "homeassistant.components.roon.async_setup_entry",
        return_value=True,
    ):

        await setup.async_setup_component(hass, "persistent_notification", {})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

        # Should go straight to link if server was discovered
        assert result["type"] == "form"
        assert result["step_id"] == "link"
        assert result["errors"] == {}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result2["errors"] == {"base": "invalid_auth"}


async def test_unexpected_exception(hass):
    """Test successful discover, but failed auth."""
    with patch(
        "homeassistant.components.roon.config_flow.RoonHub",
        return_value=RoonHubMockException(None, ["2.2.2.2"]),
    ), patch("homeassistant.components.roon.async_setup", return_value=True), patch(
        "homeassistant.components.roon.async_setup_entry",
        return_value=True,
    ):

        await setup.async_setup_component(hass, "persistent_notification", {})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

        # Should go straight to link if server was discovered
        assert result["type"] == "form"
        assert result["step_id"] == "link"
        assert result["errors"] == {}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result2["errors"] == {"base": "unknown"}
