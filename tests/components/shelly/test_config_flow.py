"""Test the Shelly config flow."""
import asyncio
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import aioshelly
import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.shelly import async_setup
from homeassistant.components.shelly.const import DOMAIN

from tests.common import MockConfigEntry

MOCK_SETTINGS = {
    "name": "Test name",
    "device": {"mac": "test-mac", "hostname": "test-host", "type": "SHSW-1"},
}
DISCOVERY_INFO = {
    "host": "1.1.1.1",
    "name": "shelly1pm-12345",
    "properties": {"id": "shelly1pm-12345"},
}
MOCK_CONFIG = {"domain": "Shelly", "coap_port": 1234}


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
        new=AsyncMock(
            return_value=Mock(
                settings=MOCK_SETTINGS,
            )
        ),
    ), patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Test name"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "model": "SHSW-1",
        "sleep_period": 0,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_title_without_name(hass):
    """Test we set the title to the hostname when the device doesn't have a name."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    settings = MOCK_SETTINGS.copy()
    settings["name"] = None
    settings["device"] = settings["device"].copy()
    settings["device"]["hostname"] = "shelly1pm-12345"
    with patch(
        "aioshelly.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": False},
    ), patch(
        "aioshelly.Device.create",
        new=AsyncMock(
            return_value=Mock(
                settings=settings,
            )
        ),
    ), patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "shelly1pm-12345"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "model": "SHSW-1",
        "sleep_period": 0,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_auth(hass):
    """Test manual configuration if auth is required."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "aioshelly.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": True},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "aioshelly.Device.create",
        new=AsyncMock(
            return_value=Mock(
                settings=MOCK_SETTINGS,
            )
        ),
    ), patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"username": "test username", "password": "test password"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "Test name"
    assert result3["data"] == {
        "host": "1.1.1.1",
        "model": "SHSW-1",
        "sleep_period": 0,
        "username": "test username",
        "password": "test password",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "error", [(asyncio.TimeoutError, "cannot_connect"), (ValueError, "unknown")]
)
async def test_form_errors_get_info(hass, error):
    """Test we handle errors."""
    exc, base_error = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("aioshelly.get_info", side_effect=exc):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": base_error}


@pytest.mark.parametrize(
    "error", [(asyncio.TimeoutError, "cannot_connect"), (ValueError, "unknown")]
)
async def test_form_errors_test_connection(hass, error):
    """Test we handle errors."""

    config = MOCK_CONFIG.copy()
    await async_setup(hass, config)

    exc, base_error = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aioshelly.get_info", return_value={"mac": "test-mac", "auth": False}
    ), patch("aioshelly.Device.create", new=AsyncMock(side_effect=exc)):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": base_error}


async def test_form_already_configured(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aioshelly.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": False},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

        assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result2["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data["host"] == "1.1.1.1"


async def test_user_setup_ignored_device(hass):
    """Test user can successfully setup an ignored device."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="test-mac",
        data={"host": "0.0.0.0"},
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    settings = MOCK_SETTINGS.copy()
    settings["device"]["type"] = "SHSW-1"
    settings["fw"] = "20201124-092534/v1.9.0@57ac4ad8"

    with patch(
        "aioshelly.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": False},
    ), patch(
        "aioshelly.Device.create",
        new=AsyncMock(
            return_value=Mock(
                settings=settings,
            )
        ),
    ), patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

        assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    # Test config entry got updated with latest IP
    assert entry.data["host"] == "1.1.1.1"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_firmware_unsupported(hass):
    """Test we abort if device firmware is unsupported."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("aioshelly.get_info", side_effect=aioshelly.FirmwareUnsupported):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

        assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result2["reason"] == "unsupported_firmware"


@pytest.mark.parametrize(
    "error",
    [
        (aiohttp.ClientResponseError(Mock(), (), status=400), "cannot_connect"),
        (aiohttp.ClientResponseError(Mock(), (), status=401), "invalid_auth"),
        (asyncio.TimeoutError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_form_auth_errors_test_connection(hass, error):
    """Test we handle errors in authenticated devices."""

    exc, base_error = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("aioshelly.get_info", return_value={"mac": "test-mac", "auth": True}):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    with patch(
        "aioshelly.Device.create",
        new=AsyncMock(side_effect=exc),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"username": "test username", "password": "test password"},
        )
    assert result3["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result3["errors"] == {"base": base_error}


async def test_zeroconf(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "aioshelly.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": False},
    ), patch(
        "aioshelly.Device.create",
        new=AsyncMock(
            return_value=Mock(
                settings=MOCK_SETTINGS,
            )
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {}
        context = next(
            flow["context"]
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert context["title_placeholders"]["name"] == "shelly1pm-12345"
        assert context["confirm_only"] is True
    with patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Test name"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "model": "SHSW-1",
        "sleep_period": 0,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_sleeping_device(hass):
    """Test sleeping device configuration via zeroconf."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "aioshelly.get_info",
        return_value={
            "mac": "test-mac",
            "type": "SHSW-1",
            "auth": False,
            "sleep_mode": True,
        },
    ), patch(
        "aioshelly.Device.create",
        new=AsyncMock(
            return_value=Mock(
                settings={
                    "name": "Test name",
                    "device": {
                        "mac": "test-mac",
                        "hostname": "test-host",
                        "type": "SHSW-1",
                    },
                    "sleep_mode": {"period": 10, "unit": "m"},
                },
            )
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {}
        context = next(
            flow["context"]
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert context["title_placeholders"]["name"] == "shelly1pm-12345"
    with patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Test name"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "model": "SHSW-1",
        "sleep_period": 600,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "error",
    [
        (aiohttp.ClientResponseError(Mock(), (), status=400), "cannot_connect"),
        (asyncio.TimeoutError, "cannot_connect"),
    ],
)
async def test_zeroconf_sleeping_device_error(hass, error):
    """Test sleeping device configuration via zeroconf with error."""
    exc = error
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "aioshelly.get_info",
        return_value={
            "mac": "test-mac",
            "type": "SHSW-1",
            "auth": False,
            "sleep_mode": True,
        },
    ), patch(
        "aioshelly.Device.create",
        new=AsyncMock(side_effect=exc),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "cannot_connect"


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
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data["host"] == "1.1.1.1"


async def test_zeroconf_firmware_unsupported(hass):
    """Test we abort if device firmware is unsupported."""
    with patch("aioshelly.get_info", side_effect=aioshelly.FirmwareUnsupported):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "unsupported_firmware"


async def test_zeroconf_cannot_connect(hass):
    """Test we get the form."""
    with patch("aioshelly.get_info", side_effect=asyncio.TimeoutError):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "cannot_connect"


async def test_zeroconf_require_auth(hass):
    """Test zeroconf if auth is required."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "aioshelly.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": True},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {}

    with patch(
        "aioshelly.Device.create",
        new=AsyncMock(
            return_value=Mock(
                settings=MOCK_SETTINGS,
            )
        ),
    ), patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test username", "password": "test password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Test name"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "model": "SHSW-1",
        "sleep_period": 0,
        "username": "test username",
        "password": "test password",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
