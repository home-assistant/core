"""Test the Wyoming config flow."""
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from wyoming.info import Info

from homeassistant import config_entries
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.components.wyoming.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import EMPTY_INFO, STT_INFO, TTS_INFO

from tests.common import MockConfigEntry

ADDON_DISCOVERY = HassioServiceInfo(
    config={
        "addon": "Piper",
        "uri": "tcp://mock-piper:10200",
    },
    name="Piper",
    slug="mock_piper",
    uuid="1234",
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form_stt(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=STT_INFO,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 1234,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test ASR"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "port": 1234,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_tts(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=TTS_INFO,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 1234,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test TTS"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "port": 1234,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 1234,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_no_supported_services(hass: HomeAssistant) -> None:
    """Test we handle no supported services error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=EMPTY_INFO,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 1234,
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "no_services"


@pytest.mark.parametrize("info", [STT_INFO, TTS_INFO])
async def test_hassio_addon_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    snapshot: SnapshotAssertion,
    info: Info,
) -> None:
    """Test config flow initiated by Supervisor."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=ADDON_DISCOVERY,
        context={"source": config_entries.SOURCE_HASSIO},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "hassio_confirm"
    assert result.get("description_placeholders") == {"addon": "Piper"}

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=info,
    ) as mock_wyoming:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2 == snapshot

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_wyoming.mock_calls) == 1


async def test_hassio_addon_already_configured(hass: HomeAssistant) -> None:
    """Test we abort discovery if the add-on is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        data={"host": "mock-piper", "port": "10200"},
        unique_id="1234",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=ADDON_DISCOVERY,
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_hassio_addon_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=ADDON_DISCOVERY,
        context={"source": config_entries.SOURCE_HASSIO},
    )

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") == {"base": "cannot_connect"}


async def test_hassio_addon_no_supported_services(hass: HomeAssistant) -> None:
    """Test we handle no supported services error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=ADDON_DISCOVERY,
        context={"source": config_entries.SOURCE_HASSIO},
    )

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=EMPTY_INFO,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2.get("type") == FlowResultType.ABORT
    assert result2.get("reason") == "no_services"
