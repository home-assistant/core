"""Test the Hi-Link HLK-SW16 config flow."""
import asyncio
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.hlk_sw16.const import DOMAIN
from homeassistant.core import HomeAssistant


class MockSW16Client:
    """Class to mock the SW16Client client."""

    def __init__(self, fail):
        """Initialise client with failure modes."""
        self.fail = fail
        self.disconnect_callback = None
        self.in_transaction = False
        self.active_transaction = None

    async def setup(self):
        """Mock successful setup."""
        fut = asyncio.Future()
        fut.set_result(True)
        return fut

    async def status(self):
        """Mock status based on failure mode."""
        self.in_transaction = True
        self.active_transaction = asyncio.Future()
        if self.fail:
            if self.disconnect_callback:
                self.disconnect_callback()
            return await self.active_transaction
        else:
            self.active_transaction.set_result(True)
            return self.active_transaction

    def stop(self):
        """Mock client stop."""
        self.in_transaction = False
        self.active_transaction = None


async def create_mock_hlk_sw16_connection(fail):
    """Create a mock HLK-SW16 client."""
    client = MockSW16Client(fail)
    await client.setup()
    return client


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    conf = {
        "host": "127.0.0.1",
        "port": 8080,
    }

    mock_hlk_sw16_connection = await create_mock_hlk_sw16_connection(False)

    with patch(
        "homeassistant.components.hlk_sw16.config_flow.create_hlk_sw16_connection",
        return_value=mock_hlk_sw16_connection,
    ), patch(
        "homeassistant.components.hlk_sw16.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.hlk_sw16.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            conf,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "127.0.0.1:8080"
    assert result2["data"] == {
        "host": "127.0.0.1",
        "port": 8080,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    mock_hlk_sw16_connection = await create_mock_hlk_sw16_connection(False)

    with patch(
        "homeassistant.components.hlk_sw16.config_flow.create_hlk_sw16_connection",
        return_value=mock_hlk_sw16_connection,
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result3["type"] == "form"
    assert result3["errors"] == {}

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        conf,
    )

    assert result4["type"] == "abort"
    assert result4["reason"] == "already_configured"


async def test_import(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    conf = {
        "host": "127.0.0.1",
        "port": 8080,
    }

    mock_hlk_sw16_connection = await create_mock_hlk_sw16_connection(False)

    with patch(
        "homeassistant.components.hlk_sw16.config_flow.connect_client",
        return_value=mock_hlk_sw16_connection,
    ), patch(
        "homeassistant.components.hlk_sw16.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.hlk_sw16.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            conf,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "127.0.0.1:8080"
    assert result2["data"] == {
        "host": "127.0.0.1",
        "port": 8080,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_data(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_hlk_sw16_connection = await create_mock_hlk_sw16_connection(True)

    conf = {
        "host": "127.0.0.1",
        "port": 8080,
    }

    with patch(
        "homeassistant.components.hlk_sw16.config_flow.connect_client",
        return_value=mock_hlk_sw16_connection,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            conf,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    conf = {
        "host": "127.0.0.1",
        "port": 8080,
    }

    with patch(
        "homeassistant.components.hlk_sw16.config_flow.connect_client",
        side_effect=TimeoutError,
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            conf,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
