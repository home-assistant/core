"""Test the roon config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.roon.const import DOMAIN


class RoonApiMock:
    """Class to mock the Roon API for testing."""

    @property
    def token(self):
        """Return a good authentication key."""
        return "good_token"

    @property
    def core_id(self):
        """Return the roon host."""
        return "core_id"

    def stop(self):
        """Stop socket and discovery."""
        return


class RoonApiMockNoToken(RoonApiMock):
    """Class to mock the Roon API for testing, with failed authorisation."""

    @property
    def token(self):
        """Return a bad authentication key."""
        return None


class RoonApiMockException(RoonApiMock):
    """Class to mock the Roon API for testing, throws an unexpected exception."""

    @property
    def token(self):
        """Throw exception."""
        raise Exception


class RoonDiscoveryMock:
    """Class to mock Roon Discovery for testing."""

    def all(self):
        """Return a discovered roon server."""
        return ["2.2.2.2"]

    def stop(self):
        """Stop discovery running."""
        return


class RoonDiscoveryFailedMock(RoonDiscoveryMock):
    """Class to mock Roon Discovery for testing, with no servers discovered."""

    def all(self):
        """Return no discovered roon servers."""
        return []


async def test_successful_discovery_and_auth(hass):
    """Test when discovery and auth both work ok."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "homeassistant.components.roon.config_flow.RoonApi",
        return_value=RoonApiMock(),
    ), patch(
        "homeassistant.components.roon.config_flow.RoonDiscovery",
        return_value=RoonDiscoveryMock(),
    ), patch(
        "homeassistant.components.roon.async_setup", return_value=True
    ), patch(
        "homeassistant.components.roon.async_setup_entry",
        return_value=True,
    ):

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

    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "homeassistant.components.roon.config_flow.RoonApi",
        return_value=RoonApiMock(),
    ), patch(
        "homeassistant.components.roon.config_flow.RoonDiscovery",
        return_value=RoonDiscoveryFailedMock(),
    ), patch(
        "homeassistant.components.roon.async_setup", return_value=True
    ), patch(
        "homeassistant.components.roon.async_setup_entry",
        return_value=True,
    ):

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

    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "homeassistant.components.roon.config_flow.RoonApi",
        return_value=RoonApiMockNoToken(),
    ), patch(
        "homeassistant.components.roon.config_flow.RoonDiscovery",
        return_value=RoonDiscoveryMock(),
    ), patch(
        "homeassistant.components.roon.config_flow.TIMEOUT",
        0,
    ), patch(
        "homeassistant.components.roon.config_flow.AUTHENTICATE_TIMEOUT",
        0.01,
    ), patch(
        "homeassistant.components.roon.async_setup", return_value=True
    ), patch(
        "homeassistant.components.roon.async_setup_entry",
        return_value=True,
    ):

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
    """Test successful discover, and unexpected exception during auth."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "homeassistant.components.roon.config_flow.RoonApi",
        return_value=RoonApiMockException(),
    ), patch(
        "homeassistant.components.roon.config_flow.RoonDiscovery",
        return_value=RoonDiscoveryMock(),
    ), patch(
        "homeassistant.components.roon.async_setup", return_value=True
    ), patch(
        "homeassistant.components.roon.async_setup_entry",
        return_value=True,
    ):

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
