"""Test the Shelly config flow."""
import asyncio

import pytest

from homeassistant import config_entries, setup
from homeassistant.components.shelly.const import DOMAIN

from tests.async_mock import AsyncMock, Mock, patch
from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "aioshelly.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": False},
    ), patch(
        "aioshelly.Device.create",
        return_value=Mock(
            shutdown=AsyncMock(),
            settings={"name": "Test name", "device": {"mac": "test-mac"}},
        ),
    ), patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.1.1.1"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Test name"
    assert result2["data"] == {
        "host": "1.1.1.1",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_auth(hass):
    """Test we can't manually configure if auth is required."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "aioshelly.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": True},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.1.1.1"},
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "auth_not_supported"


@pytest.mark.parametrize(
    "error", [(asyncio.TimeoutError, "cannot_connect"), (ValueError, "unknown")]
)
async def test_form_errors_get_info(hass, error):
    """Test we handle errors."""
    exc, base_error = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aioshelly.get_info", side_effect=exc,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.1.1.1"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": base_error}


@pytest.mark.parametrize(
    "error", [(asyncio.TimeoutError, "cannot_connect"), (ValueError, "unknown")]
)
async def test_form_errors_test_connection(hass, error):
    """Test we handle errors."""
    exc, base_error = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("aioshelly.get_info", return_value={"auth": False}), patch(
        "aioshelly.Device.create", side_effect=exc,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.1.1.1"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": base_error}


async def test_zeroconf(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "aioshelly.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data={"host": "1.1.1.1", "name": "shelly1pm-12345"},
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == "form"
        assert result["errors"] == {}

    with patch(
        "aioshelly.Device.create",
        return_value=Mock(
            shutdown=AsyncMock(),
            settings={"name": "Test name", "device": {"mac": "test-mac"}},
        ),
    ), patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {},)

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Test name"
    assert result2["data"] == {
        "host": "1.1.1.1",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "error", [(asyncio.TimeoutError, "cannot_connect"), (ValueError, "unknown")]
)
async def test_zeroconf_confirm_error(hass, error):
    """Test we get the form."""
    exc, base_error = error
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "aioshelly.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data={"host": "1.1.1.1", "name": "shelly1pm-12345"},
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == "form"
        assert result["errors"] == {}

    with patch(
        "aioshelly.Device.create", side_effect=exc,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {},)

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": base_error}


async def test_zeroconf_already_configured(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    with patch(
        "aioshelly.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data={"host": "1.1.1.1", "name": "shelly1pm-12345"},
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data["host"] == "1.1.1.1"


async def test_zeroconf_cannot_connect(hass):
    """Test we get the form."""
    with patch(
        "aioshelly.get_info", side_effect=asyncio.TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data={"host": "1.1.1.1", "name": "shelly1pm-12345"},
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == "abort"
        assert result["reason"] == "cannot_connect"


async def test_zeroconf_require_auth(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "aioshelly.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": True},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data={"host": "1.1.1.1", "name": "shelly1pm-12345"},
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == "abort"
        assert result["reason"] == "auth_not_supported"


async def test_zeroconf_not_shelly(hass):
    """Test we filter out non-shelly devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={"host": "1.1.1.1", "name": "notshelly"},
        context={"source": config_entries.SOURCE_ZEROCONF},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "not_shelly"
