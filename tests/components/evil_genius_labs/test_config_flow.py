"""Test the Evil Genius Labs config flow."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components.evil_genius_labs.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util.json import JsonObjectType


@contextmanager
def _patch_device(
    all_fixture: dict[str, Any],
    info_fixture: JsonObjectType,
    product_fixture: dict[str, str],
) -> Generator[None]:
    """Patch a reachable device and the entry setup."""
    with (
        patch("pyevilgenius.EvilGeniusDevice.get_all", return_value=all_fixture),
        patch("pyevilgenius.EvilGeniusDevice.get_info", return_value=info_fixture),
        patch(
            "pyevilgenius.EvilGeniusDevice.get_product", return_value=product_fixture
        ),
        patch(
            "homeassistant.components.evil_genius_labs.async_setup_entry",
            return_value=True,
        ),
    ):
        yield


async def test_form(
    hass: HomeAssistant, all_fixture, info_fixture, product_fixture
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "pyevilgenius.EvilGeniusDevice.get_all",
            return_value=all_fixture,
        ),
        patch(
            "pyevilgenius.EvilGeniusDevice.get_info",
            return_value=info_fixture,
        ),
        patch(
            "pyevilgenius.EvilGeniusDevice.get_product",
            return_value=product_fixture,
        ),
        patch(
            "homeassistant.components.evil_genius_labs.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Fibonacci256-23D4"
    assert result2["data"] == {
        "host": "1.1.1.1",
    }
    assert result2["result"].unique_id == "1923d4"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    all_fixture: dict[str, Any],
    info_fixture: JsonObjectType,
    product_fixture: dict[str, str],
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyevilgenius.EvilGeniusDevice.get_all",
        side_effect=aiohttp.ClientError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    assert "Unable to connect" in caplog.text

    with _patch_device(all_fixture, info_fixture, product_fixture):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.1.1.1"}
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_timeout(
    hass: HomeAssistant,
    all_fixture: dict[str, Any],
    info_fixture: JsonObjectType,
    product_fixture: dict[str, str],
) -> None:
    """Test we handle timeout error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyevilgenius.EvilGeniusDevice.get_all",
        side_effect=TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "timeout"}

    with _patch_device(all_fixture, info_fixture, product_fixture):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.1.1.1"}
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_unknown(
    hass: HomeAssistant,
    all_fixture: dict[str, Any],
    info_fixture: JsonObjectType,
    product_fixture: dict[str, str],
) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyevilgenius.EvilGeniusDevice.get_all",
        side_effect=ValueError("BOOM"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    with _patch_device(all_fixture, info_fixture, product_fixture):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.1.1.1"}
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
