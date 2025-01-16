"""Test the Wyoming config flow."""

from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from wyoming.info import Info

from homeassistant import config_entries
from homeassistant.components.wyoming.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import EMPTY_INFO, SATELLITE_INFO, STT_INFO, TTS_INFO

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

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=IPv4Address("127.0.0.1"),
    ip_addresses=[IPv4Address("127.0.0.1")],
    port=12345,
    hostname="localhost",
    type="_wyoming._tcp.local.",
    name="test_zeroconf_name._wyoming._tcp.local.",
    properties={},
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form_stt(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
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

    assert result2["type"] is FlowResultType.CREATE_ENTRY
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
    assert result["type"] is FlowResultType.FORM
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

    assert result2["type"] is FlowResultType.CREATE_ENTRY
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

    assert result2["type"] is FlowResultType.FORM
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

    assert result2["type"] is FlowResultType.ABORT
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

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "hassio_confirm"
    assert result.get("description_placeholders") == {"addon": "Piper"}

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=info,
    ) as mock_wyoming:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2 == snapshot

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_wyoming.mock_calls) == 1


async def test_hassio_addon_already_configured(hass: HomeAssistant) -> None:
    """Test we abort discovery if the add-on is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "mock-piper", "port": 10200},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=ADDON_DISCOVERY,
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    assert entry.unique_id == "1234"


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

    assert result2.get("type") is FlowResultType.FORM
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

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "no_services"


async def test_zeroconf_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config flow initiated by Supervisor."""
    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=SATELLITE_INFO,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=ZEROCONF_DISCOVERY,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "zeroconf_confirm"
    assert result.get("description_placeholders") == {
        "name": SATELLITE_INFO.satellite.name
    }

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2 == snapshot


async def test_zeroconf_discovery_no_port(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test discovery when the zeroconf service does not have a port."""
    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch.object(ZEROCONF_DISCOVERY, "port", None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=ZEROCONF_DISCOVERY,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "no_port"


async def test_zeroconf_discovery_no_services(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test discovery when there are no supported services on the client."""
    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=Info(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=ZEROCONF_DISCOVERY,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "no_services"


async def test_zeroconf_discovery_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config flow initiated by Supervisor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "127.0.0.1", "port": 12345},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=SATELLITE_INFO,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=ZEROCONF_DISCOVERY,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result.get("type") is FlowResultType.ABORT
    assert entry.unique_id == "test_zeroconf_name._wyoming._tcp.local._Test Satellite"
