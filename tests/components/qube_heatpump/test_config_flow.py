"""Test the Qube Heat Pump config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.qube_heatpump.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_MAC = "00:0a:5c:94:83:15"


@pytest.fixture
def mock_qube_setup():
    """Mock QubeClient and MAC lookup for config flow tests."""
    with (
        patch(
            "homeassistant.components.qube_heatpump.config_flow.QubeClient",
            autospec=True,
        ) as mock_client_cls,
        patch(
            "homeassistant.components.qube_heatpump.config_flow.async_get_mac_address",
            return_value=MOCK_MAC,
        ) as mock_mac,
    ):
        client = mock_client_cls.return_value
        client.connect = AsyncMock(return_value=True)
        client.async_get_software_version = AsyncMock(return_value="2.15")
        client.close = AsyncMock()
        yield {"client_cls": mock_client_cls, "client": client, "mac": mock_mac}


async def test_form(
    hass: HomeAssistant, mock_setup_entry: MagicMock, mock_qube_setup: dict
) -> None:
    """Test successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "qube.local"},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Qube Heat Pump"
    assert result2["data"] == {CONF_HOST: "qube.local", CONF_PORT: 502}
    assert result2["result"].unique_id == MOCK_MAC


async def test_form_cannot_connect(hass: HomeAssistant, mock_qube_setup: dict) -> None:
    """Test we handle cannot connect error."""
    mock_qube_setup["client"].connect.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_connect_exception(
    hass: HomeAssistant, mock_qube_setup: dict
) -> None:
    """Test we handle connection exception."""
    mock_qube_setup["client"].connect.side_effect = OSError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_not_qube_device(hass: HomeAssistant, mock_qube_setup: dict) -> None:
    """Test we handle device that isn't a Qube."""
    mock_qube_setup["client"].async_get_software_version.return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "not_qube_device"}


async def test_form_mac_not_found(hass: HomeAssistant, mock_qube_setup: dict) -> None:
    """Test we handle MAC address not found."""
    mock_qube_setup["mac"].return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "qube.local"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "mac_not_found"}


async def test_form_already_configured(
    hass: HomeAssistant, mock_setup_entry: MagicMock, mock_qube_setup: dict
) -> None:
    """Test we abort when device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 502},
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "qube.local"},
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
