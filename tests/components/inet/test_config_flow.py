"""Test the iNet Radio config flow."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.inet.const import CONF_MODEL_DESCRIPTION, DOMAIN
from homeassistant.config_entries import SOURCE_SSDP
from homeassistant.const import CONF_HOST, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_DESCRIPTION,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)

from .conftest import (
    MOCK_HOST,
    MOCK_MODEL_DESCRIPTION,
    MOCK_NAME,
    MOCK_SERIAL,
    MOCK_UNIQUE_ID,
    _create_mock_radio,
)

from tests.common import MockConfigEntry


def _mock_manager_with_radio(radio: MagicMock) -> MagicMock:
    """Create a mock RadioManager that returns the given radio on connect."""
    manager = MagicMock()
    manager.start = AsyncMock()
    manager.stop = AsyncMock()
    manager.connect = AsyncMock(return_value=radio)
    manager.radios = {radio.ip: radio}

    _callbacks: list = []

    def _register_discovery_callback(cb):
        _callbacks.append(cb)
        return lambda: _callbacks.remove(cb)

    manager.register_discovery_callback = _register_discovery_callback

    async def _discover():
        for cb in _callbacks:
            cb(radio)

    manager.discover = _discover

    return manager


def _mock_manager_no_radios() -> MagicMock:
    """Create a mock RadioManager with no discovered radios."""
    manager = MagicMock()
    manager.start = AsyncMock()
    manager.stop = AsyncMock()
    manager.discover = AsyncMock()
    manager.register_discovery_callback = MagicMock(return_value=lambda: None)
    manager.radios = {}
    return manager


def _mock_manager_with_delayed_mac(radio: MagicMock) -> MagicMock:
    """Create a mock RadioManager where MAC arrives after connect."""
    manager = _mock_manager_with_radio(radio)
    real_mac = radio.mac
    radio.mac = ""

    async def _connect_then_deliver_mac(*args: Any, **kwargs: Any) -> MagicMock:
        def _deliver_info_block() -> None:
            radio.mac = real_mac
            for cb in list(radio._callbacks):
                cb()

        asyncio.get_running_loop().call_soon(_deliver_info_block)
        return radio

    manager.connect = AsyncMock(side_effect=_connect_then_deliver_mac)
    return manager


async def test_manual_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful manual flow when no radios discovered."""
    radio = _create_mock_radio()
    manager_discover = _mock_manager_no_radios()
    manager_connect = _mock_manager_with_radio(radio)

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_discover,
    ):
        # No radios discovered -> goes straight to manual
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_connect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert result["data"] == {CONF_HOST: MOCK_HOST}
    assert result["result"].unique_id == MOCK_UNIQUE_ID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovery_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful flow with discovered radios."""
    radio = _create_mock_radio()
    manager = _mock_manager_with_radio(radio)

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select the discovered radio
    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device": MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert result["data"] == {CONF_HOST: MOCK_HOST}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovery_flow_manual_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test discovery flow with manual entry selection."""
    radio = _create_mock_radio()
    manager = _mock_manager_with_radio(radio)

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select manual entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device": "manual"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (TimeoutError("No response"), "cannot_connect"),
        (RuntimeError("Unexpected"), "unknown"),
    ],
)
async def test_connection_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    error_key: str,
) -> None:
    """Test connection failure shows error and allows recovery."""
    manager_fail = _mock_manager_no_radios()
    manager_fail.connect = AsyncMock(side_effect=side_effect)

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_fail,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    # Try connecting and fail
    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_fail,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.200"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    # Recover with correct host
    radio = _create_mock_radio()
    manager_ok = _mock_manager_with_radio(radio)

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_ok,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we abort if the radio is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        unique_id=MOCK_UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    radio = _create_mock_radio()
    manager_discover = _mock_manager_no_radios()
    manager_connect = _mock_manager_with_radio(radio)

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_discover,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_connect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


MOCK_SSDP_DISCOVERY = SsdpServiceInfo(
    ssdp_usn=f"uuid:82168216-0000-0000-0000-{MOCK_SERIAL}::urn:schemas-upnp-org:device:MediaRenderer:1",
    ssdp_st="urn:schemas-upnp-org:device:MediaRenderer:1",
    ssdp_location=f"http://{MOCK_HOST}:80/upnp/device.xml",
    upnp={
        ATTR_UPNP_FRIENDLY_NAME: MOCK_NAME,
        ATTR_UPNP_MANUFACTURER: "Busch-Jaeger",
        ATTR_UPNP_MODEL_NAME: "Radio iNet",
        ATTR_UPNP_MODEL_DESCRIPTION: MOCK_MODEL_DESCRIPTION,
        ATTR_UPNP_SERIAL: MOCK_SERIAL,
    },
)


async def test_ssdp_discovery(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test SSDP discovery flow."""
    radio = _create_mock_radio()
    manager = _mock_manager_with_radio(radio)

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_SSDP},
            data=MOCK_SSDP_DISCOVERY,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_MODEL_DESCRIPTION: MOCK_MODEL_DESCRIPTION,
    }
    assert result["result"].unique_id == MOCK_UNIQUE_ID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_ssdp_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test SSDP discovery aborts when already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        unique_id=MOCK_UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=MOCK_SSDP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_updates_host(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test SSDP discovery updates host for existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.200"},
        unique_id=MOCK_UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=MOCK_SSDP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == MOCK_HOST


async def test_ssdp_no_serial(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts when no serial number."""
    discovery = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_location=f"http://{MOCK_HOST}:80/upnp/device.xml",
        upnp={
            ATTR_UPNP_FRIENDLY_NAME: MOCK_NAME,
            ATTR_UPNP_MANUFACTURER: "Busch-Jaeger",
            ATTR_UPNP_MODEL_NAME: "Radio iNet",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=discovery,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_no_location(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts when ssdp_location is missing."""
    discovery = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        upnp={
            ATTR_UPNP_FRIENDLY_NAME: MOCK_NAME,
            ATTR_UPNP_MANUFACTURER: "Busch-Jaeger",
            ATTR_UPNP_MODEL_NAME: "Radio iNet",
            ATTR_UPNP_SERIAL: MOCK_SERIAL,
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=discovery,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_cannot_connect(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts when device is unreachable."""
    manager = _mock_manager_no_radios()
    manager.connect = AsyncMock(side_effect=TimeoutError)

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_SSDP},
            data=MOCK_SSDP_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_flow_aborts_when_ssdp_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow aborts if device was already added via SSDP."""
    radio = _create_mock_radio()
    manager = _mock_manager_with_radio(radio)

    # First: set up via SSDP
    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_SSDP},
            data=MOCK_SSDP_DISCOVERY,
        )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Second: try to add via user/manual flow
    radio2 = _create_mock_radio()
    manager2 = _mock_manager_with_delayed_mac(radio2)
    manager_discover = _mock_manager_no_radios()
    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_discover,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager2,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_aborts_when_user_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test SSDP discovery aborts if device was already added via user flow."""
    radio = _create_mock_radio()
    manager = _mock_manager_with_delayed_mac(radio)

    # First: set up via user/manual flow
    manager_discover = _mock_manager_no_radios()
    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_discover,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_UNIQUE_ID

    # Second: SSDP discovers the same device
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=MOCK_SSDP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
