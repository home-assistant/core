"""Test the Ollama config flow."""

import asyncio
from unittest.mock import patch

from httpx import ConnectError
import pytest

from homeassistant import config_entries
from homeassistant.components import ollama
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_MODEL = "test_model:latest"


async def test_form(hass: HomeAssistant) -> None:
    """Test flow when the model is already downloaded."""
    # Pretend we already set up a config entry.
    hass.config.components.add(ollama.DOMAIN)
    MockConfigEntry(
        domain=ollama.DOMAIN,
        state=config_entries.ConfigEntryState.LOADED,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        ollama.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.ollama.config_flow.ollama.AsyncClient.list",
            # test model is already "downloaded"
            return_value={"models": [{"model": TEST_MODEL}]},
        ),
        patch(
            "homeassistant.components.ollama.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        # Step 1: URL
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {ollama.CONF_URL: "http://localhost:11434"}
        )
        await hass.async_block_till_done()

        # Step 2: model
        assert result2["type"] is FlowResultType.FORM
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {ollama.CONF_MODEL: TEST_MODEL}
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"] == {
        ollama.CONF_URL: "http://localhost:11434",
        ollama.CONF_MODEL: TEST_MODEL,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_need_download(hass: HomeAssistant) -> None:
    """Test flow when a model needs to be downloaded."""
    # Pretend we already set up a config entry.
    hass.config.components.add(ollama.DOMAIN)
    MockConfigEntry(
        domain=ollama.DOMAIN,
        state=config_entries.ConfigEntryState.LOADED,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        ollama.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    pull_ready = asyncio.Event()
    pull_called = asyncio.Event()
    pull_model: str | None = None

    async def pull(self, model: str, *args, **kwargs) -> None:
        nonlocal pull_model

        async with asyncio.timeout(1):
            await pull_ready.wait()

        pull_model = model
        pull_called.set()

    with (
        patch(
            "homeassistant.components.ollama.config_flow.ollama.AsyncClient.list",
            # No models are downloaded
            return_value={},
        ),
        patch(
            "homeassistant.components.ollama.config_flow.ollama.AsyncClient.pull",
            pull,
        ),
        patch(
            "homeassistant.components.ollama.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        # Step 1: URL
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {ollama.CONF_URL: "http://localhost:11434"}
        )
        await hass.async_block_till_done()

        # Step 2: model
        assert result2["type"] is FlowResultType.FORM
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {ollama.CONF_MODEL: TEST_MODEL}
        )
        await hass.async_block_till_done()

        # Step 3: download
        assert result3["type"] is FlowResultType.SHOW_PROGRESS
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
        )
        await hass.async_block_till_done()

        # Run again without the task finishing.
        # We should still be downloading.
        assert result4["type"] is FlowResultType.SHOW_PROGRESS
        result4 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
        )
        await hass.async_block_till_done()
        assert result4["type"] is FlowResultType.SHOW_PROGRESS

        # Signal fake pull method to complete
        pull_ready.set()
        async with asyncio.timeout(1):
            await pull_called.wait()

        assert pull_model == TEST_MODEL

        # Step 4: finish
        result5 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
        )

    assert result5["type"] is FlowResultType.CREATE_ENTRY
    assert result5["data"] == {
        ollama.CONF_URL: "http://localhost:11434",
        ollama.CONF_MODEL: TEST_MODEL,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_options(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test the options form."""
    options_flow = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    options = await hass.config_entries.options.async_configure(
        options_flow["flow_id"],
        {
            ollama.CONF_PROMPT: "test prompt",
            ollama.CONF_MAX_HISTORY: 100,
            ollama.CONF_NUM_CTX: 32768,
        },
    )
    await hass.async_block_till_done()
    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert options["data"] == {
        ollama.CONF_PROMPT: "test prompt",
        ollama.CONF_MAX_HISTORY: 100,
        ollama.CONF_NUM_CTX: 32768,
    }


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ConnectError(message=""), "cannot_connect"),
        (RuntimeError(), "unknown"),
    ],
)
async def test_form_errors(hass: HomeAssistant, side_effect, error) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        ollama.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ollama.config_flow.ollama.AsyncClient.list",
        side_effect=side_effect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {ollama.CONF_URL: "http://localhost:11434"}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}


async def test_download_error(hass: HomeAssistant) -> None:
    """Test we handle errors while downloading a model."""
    result = await hass.config_entries.flow.async_init(
        ollama.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    async def _delayed_runtime_error(*args, **kwargs):
        await asyncio.sleep(0)
        raise RuntimeError

    with (
        patch(
            "homeassistant.components.ollama.config_flow.ollama.AsyncClient.list",
            return_value={},
        ),
        patch(
            "homeassistant.components.ollama.config_flow.ollama.AsyncClient.pull",
            _delayed_runtime_error,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {ollama.CONF_URL: "http://localhost:11434"}
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.FORM
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {ollama.CONF_MODEL: TEST_MODEL}
        )
        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.SHOW_PROGRESS
        result4 = await hass.config_entries.flow.async_configure(result3["flow_id"])
        await hass.async_block_till_done()

    assert result4["type"] is FlowResultType.ABORT
    assert result4["reason"] == "download_failed"
