"""Tests for the QuickBars config flow and options flow."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

_cf = importlib.import_module("homeassistant.components.quickbars.config_flow")
DOMAIN = "quickbars"


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@dataclass
class _ZCStub:
    """Minimal stand-in for ZeroconfServiceInfo."""

    ip_address: Any
    ip_addresses: list[Any]
    port: int
    hostname: str
    type: str
    name: str
    properties: dict[str, Any]

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key: str):
        return getattr(self, key)


@pytest.fixture
def patch_client_all():
    """Patch QuickBarsClient with sensible defaults."""
    with patch(
        "homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True
    ) as cls:
        inst = cls.return_value
        inst.get_pair_code = AsyncMock(return_value={"sid": "sid1"})
        inst.confirm_pair = AsyncMock(
            return_value={
                "id": "QB-1234",
                "name": "QuickBars TV",
                "port": 9123,
                "has_token": False,
            }
        )
        inst.set_credentials = AsyncMock(return_value={"ok": True})
        yield inst


def create_zc_stub(ip="192.0.2.20", port=9123, props=None):
    """Create a zeroconf stub with standard values."""
    if props is None:
        props = {
            "id": "QB-1234",
            "api": "1",
            "app_version": "1.2.3",
            "name": "QuickBars TV",
        }
    return _ZCStub(
        ip_address=ip_address(ip),
        ip_addresses=[ip_address(ip)],
        port=port,
        hostname="QuickBars-1234.local.",
        type="_quickbars._tcp.local.",
        name="QuickBars-1234._quickbars._tcp.local.",
        properties=props,
    )


# ---------------------------------------------------------------------------
# CONFIG FLOW TESTS
# ---------------------------------------------------------------------------


async def test_user_flow_success_paths(hass: HomeAssistant, patch_client_all) -> None:
    """Test both user flow paths - with and without token step."""
    # First test: Flow with token step
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"

    # Submit host/port
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.10", CONF_PORT: 9123}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "pair"

    # Submit pairing code
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "1234"}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "token"

    # Submit token info
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": "http://ha.local:8123", "token": "abc123"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    data = result["data"]
    assert data is not None
    assert data[CONF_HOST] == "192.0.2.10"
    assert data[CONF_PORT] == 9123

    # Remove the entry before testing the second path
    await hass.config_entries.async_remove(result["result"].entry_id)
    await hass.async_block_till_done()

    # Second test: Flow with token already set
    patch_client_all.confirm_pair.return_value.update({"has_token": True})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.0.2.20",
            CONF_PORT: 9123,
        },  # Use different IP to avoid duplicate
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "1234"}
    )
    # Should skip token step and create entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    data = result["data"]
    assert data is not None
    assert data[CONF_HOST] == "192.0.2.20"  # Check different IP


async def test_user_flow_error_invalid_credentials(hass: HomeAssistant) -> None:
    """Test error when credentials are invalid at token step."""
    with patch(
        "homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True
    ) as cls:
        cls.return_value.get_pair_code = AsyncMock(return_value={"sid": "sid1"})
        cls.return_value.confirm_pair = AsyncMock(
            return_value={
                "id": "QB-5555",
                "name": "QB",
                "port": 9123,
                "has_token": False,
            }
        )
        cls.return_value.set_credentials = AsyncMock(
            return_value={"ok": False, "reason": "creds_invalid"}
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.44", CONF_PORT: 9123}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "0000"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "http://x", "token": "y"}
        )
        assert result["type"] is FlowResultType.FORM and result["step_id"] == "token"
        errors = result["errors"]
        assert errors is not None and errors["base"] == "creds_invalid"


async def test_user_flow_error_tv_unreachable_at_token(hass: HomeAssistant) -> None:
    """Test error when TV becomes unreachable at token step."""
    with patch(
        "homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True
    ) as cls:
        cls.return_value.get_pair_code = AsyncMock(return_value={"sid": "sid1"})
        cls.return_value.confirm_pair = AsyncMock(
            return_value={
                "id": "QB-6666",
                "name": "QB",
                "port": 9123,
                "has_token": False,
            }
        )
        cls.return_value.set_credentials = AsyncMock(side_effect=ClientError("boom"))

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.55", CONF_PORT: 9123}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "0000"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "http://x", "token": "y"}
        )
        assert result["type"] is FlowResultType.FORM and result["step_id"] == "token"
        errors = result["errors"]
        assert errors is not None and errors["base"] == "tv_unreachable"


# Split the error cases into separate tests to avoid flow interference


async def test_user_flow_error_tv_unreachable(hass: HomeAssistant) -> None:
    """Test error handling when TV is unreachable."""
    with patch(
        "homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True
    ) as cls:
        cls.return_value.get_pair_code = AsyncMock(side_effect=TimeoutError)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_PORT: 9123}
        )
        assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
        errors = result["errors"]
        assert errors is not None and errors["base"] == "tv_unreachable"


async def test_user_flow_error_no_unique_id(hass: HomeAssistant) -> None:
    """Test error when no unique ID is returned."""
    with patch(
        "homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True
    ) as cls:
        cls.return_value.get_pair_code = AsyncMock(return_value={"sid": "sid1"})
        cls.return_value.confirm_pair = AsyncMock(return_value={})  # No ID

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.5", CONF_PORT: 9123}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "1234"}
        )
        assert result["type"] is FlowResultType.FORM and result["step_id"] == "pair"
        errors = result["errors"]
        assert errors is not None and errors["base"] == "no_unique_id"


async def test_edge_cases(hass: HomeAssistant) -> None:
    """Test edge cases in the config flow."""
    # Case 1: Missing URL in Home Assistant
    with (
        patch(
            "homeassistant.components.quickbars.config_flow.QuickBarsClient",
            autospec=True,
        ) as cls,
        patch(
            "homeassistant.components.quickbars.config_flow.get_url",
            side_effect=HomeAssistantError("no url"),
        ),
    ):
        cls.return_value.get_pair_code = AsyncMock(return_value={"sid": "sid1"})
        cls.return_value.confirm_pair = AsyncMock(
            return_value={
                "id": "QB-8888",
                "name": "QB",
                "port": 9123,
                "has_token": True,
            }
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_PORT: 9123}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "0000"}
        )
        # Should still succeed despite missing URL
        assert result["type"] is FlowResultType.CREATE_ENTRY

    # Case 2: Default port when missing
    with patch(
        "homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True
    ) as cls:
        cls.return_value.get_pair_code = AsyncMock(return_value={"sid": "sid1"})
        cls.return_value.confirm_pair = AsyncMock(
            return_value={
                "id": "QB-7777",
                "name": "QB",
                "port": None,
                "has_token": True,
            }
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_PORT: 9123}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "1234"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        data = result["data"]
        assert data is not None and data[CONF_PORT] == 9123


async def test_zeroconf_flows(hass: HomeAssistant, patch_client_all) -> None:
    """Test zeroconf discovery flows."""
    # Standard flow - discover and pair
    zc = create_zc_stub(
        ip="192.0.2.20",
        props={
            "id": "QB-9999",
            "api": "1",
            "app_version": "1.2.3",
            "name": "QuickBars TV",
        },
    )

    with patch(
        "homeassistant.components.quickbars.config_flow.decode_zeroconf",
        return_value=(
            "192.0.2.20",
            9123,
            {
                "id": "QB-9999",
                "api": "1",
                "app_version": "1.2.3",
                "name": "QuickBars TV",
            },
            "QuickBars-9999.local.",
            "QuickBars-9999._quickbars._tcp.local.",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zc
        )
    assert (
        result["type"] is FlowResultType.FORM
        and result["step_id"] == "zeroconf_confirm"
    )

    # Re-enter the confirm step with None to test the getattr/fallback logic (lines 230-236)
    result_reentry = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result_reentry["type"] is FlowResultType.FORM
    assert result_reentry["step_id"] == "zeroconf_confirm"

    # Update the patch_client_all mock to use the new unique_id
    patch_client_all.confirm_pair.return_value.update({"id": "QB-9999"})

    # Confirm discovery
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "pair"

    # Complete pairing
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "9999"}
    )
    if result["type"] is FlowResultType.FORM:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "http://ha.local:8123", "token": "abc123"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_updates_existing_entry(hass: HomeAssistant) -> None:
    """Test that zeroconf discovery updates an existing entry."""
    # Create an entry to be updated
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="QB-1234",
        data={CONF_HOST: "192.0.2.10", CONF_PORT: 9123, "id": "QB-1234"},
    )
    entry.add_to_hass(hass)

    # Create a discovery with new IP/port
    zc = create_zc_stub(ip="192.0.2.55", port=9999)

    with patch(
        "homeassistant.components.quickbars.config_flow.decode_zeroconf",
        return_value=(
            "192.0.2.55",
            9999,
            {
                "id": "QB-1234",
                "api": "1",
                "app_version": "1.2.3",
                "name": "QuickBars TV",
            },
            "QuickBars-1234.local.",
            "QuickBars-1234._quickbars._tcp.local.",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zc
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Get the updated entry
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated is not None
    assert updated.data[CONF_HOST] == "192.0.2.55"
    assert updated.data[CONF_PORT] == 9999


async def test_zeroconf_error_cases(hass: HomeAssistant) -> None:
    """Test error handling in zeroconf flows."""
    # Case 1: Missing host/port
    zc = _ZCStub(
        ip_address=ip_address("192.0.2.1"),
        ip_addresses=[ip_address("192.0.2.1")],
        port=0,
        hostname="h",
        type="_quickbars._tcp.local.",
        name="n",
        properties={},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zc
    )
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "unknown"

    # Case 2: TV unreachable after confirm
    zc = create_zc_stub(ip="1.2.3.4")

    with (
        patch(
            "homeassistant.components.quickbars.config_flow.decode_zeroconf",
            return_value=(
                "1.2.3.4",
                9123,
                {"id": "QB-1234", "api": "1", "app_version": "1.2.3", "name": "QB"},
                "h",
                "n",
            ),
        ),
        patch(
            "homeassistant.components.quickbars.config_flow.QuickBarsClient",
            autospec=True,
        ) as cls,
    ):
        cls.return_value.get_pair_code = AsyncMock(side_effect=OSError("down"))

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zc
        )
        assert (
            result["type"] is FlowResultType.FORM
            and result["step_id"] == "zeroconf_confirm"
        )

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
        errors = result["errors"]
        assert errors is not None and errors["base"] == "tv_unreachable"
