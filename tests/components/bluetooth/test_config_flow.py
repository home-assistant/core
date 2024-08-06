"""Test the bluetooth config flow."""

from unittest.mock import patch

from bluetooth_adapters import DEFAULT_ADDRESS, AdapterDetails
import pytest

from homeassistant import config_entries
from homeassistant.components.bluetooth.const import (
    CONF_ADAPTER,
    CONF_DETAILS,
    CONF_PASSIVE,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures(
    "macos_adapter", "mock_bleak_scanner_start", "mock_bluetooth_adapters"
)
async def test_options_flow_disabled_not_setup(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test options are disabled if the integration has not been setup."""
    await async_setup_component(hass, "config", {})
    entry = MockConfigEntry(
        domain=DOMAIN, data={}, options={}, unique_id=DEFAULT_ADDRESS
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/get",
            "domain": "bluetooth",
        }
    )
    response = await ws_client.receive_json()
    assert response["result"][0]["supports_options"] is False
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("macos_adapter")
async def test_async_step_user_macos(hass: HomeAssistant) -> None:
    """Test setting up manually with one adapter on MacOS."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "single_adapter"
    with (
        patch("homeassistant.components.bluetooth.async_setup", return_value=True),
        patch(
            "homeassistant.components.bluetooth.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Apple Unknown MacOS Model (Core Bluetooth)"
    assert result2["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("one_adapter")
async def test_async_step_user_linux_one_adapter(hass: HomeAssistant) -> None:
    """Test setting up manually with one adapter on Linux."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "single_adapter"
    assert result["description_placeholders"] == {
        "name": "hci0 (00:00:00:00:00:01)",
        "model": "Bluetooth Adapter 5.0 (cc01:aa01)",
        "manufacturer": "ACME",
    }
    with (
        patch("homeassistant.components.bluetooth.async_setup", return_value=True),
        patch(
            "homeassistant.components.bluetooth.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "ACME Bluetooth Adapter 5.0 (00:00:00:00:00:01)"
    assert result2["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_async_step_user_linux_crashed_adapter(
    hass: HomeAssistant, crashed_adapter: None
) -> None:
    """Test setting up manually with one crashed adapter on Linux."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_adapters"


@pytest.mark.usefixtures("two_adapters")
async def test_async_step_user_linux_two_adapters(hass: HomeAssistant) -> None:
    """Test setting up manually with two adapters on Linux."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "multiple_adapters"
    assert result["data_schema"].schema["adapter"].container == {
        "hci0": "hci0 (00:00:00:00:00:01) ACME Bluetooth Adapter 5.0 (cc01:aa01)",
        "hci1": "hci1 (00:00:00:00:00:02) ACME Bluetooth Adapter 5.0 (cc01:aa01)",
    }
    with (
        patch("homeassistant.components.bluetooth.async_setup", return_value=True),
        patch(
            "homeassistant.components.bluetooth.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADAPTER: "hci1"}
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "ACME Bluetooth Adapter 5.0 (00:00:00:00:00:02)"
    assert result2["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("macos_adapter")
async def test_async_step_user_only_allows_one(hass: HomeAssistant) -> None:
    """Test setting up manually with an existing entry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DEFAULT_ADDRESS)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_adapters"


async def test_async_step_integration_discovery(hass: HomeAssistant) -> None:
    """Test setting up from integration discovery."""

    details = AdapterDetails(
        address="00:00:00:00:00:01",
        sw_version="1.23.5",
        hw_version="1.2.3",
        manufacturer="ACME",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_ADAPTER: "hci0", CONF_DETAILS: details},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {
        "name": "hci0 (00:00:00:00:00:01)",
        "model": "Unknown",
        "manufacturer": "ACME",
    }
    assert result["step_id"] == "single_adapter"
    with (
        patch("homeassistant.components.bluetooth.async_setup", return_value=True),
        patch(
            "homeassistant.components.bluetooth.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "ACME Unknown (00:00:00:00:00:01)"
    assert result2["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("one_adapter")
async def test_async_step_integration_discovery_during_onboarding_one_adapter(
    hass: HomeAssistant,
) -> None:
    """Test setting up from integration discovery during onboarding."""
    details = AdapterDetails(
        address="00:00:00:00:00:01",
        sw_version="1.23.5",
        hw_version="1.2.3",
        manufacturer="ACME",
    )

    with (
        patch("homeassistant.components.bluetooth.async_setup", return_value=True),
        patch(
            "homeassistant.components.bluetooth.async_setup_entry", return_value=True
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.onboarding.async_is_onboarded",
            return_value=False,
        ) as mock_onboarding,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_ADAPTER: "hci0", CONF_DETAILS: details},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ACME Unknown (00:00:00:00:00:01)"
    assert result["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_onboarding.mock_calls) == 1


@pytest.mark.usefixtures("two_adapters")
async def test_async_step_integration_discovery_during_onboarding_two_adapters(
    hass: HomeAssistant,
) -> None:
    """Test setting up from integration discovery during onboarding."""
    details1 = AdapterDetails(
        address="00:00:00:00:00:01",
        sw_version="1.23.5",
        hw_version="1.2.3",
        manufacturer="ACME",
    )
    details2 = AdapterDetails(
        address="00:00:00:00:00:02",
        sw_version="1.23.5",
        hw_version="1.2.3",
        manufacturer="ACME",
    )

    with (
        patch("homeassistant.components.bluetooth.async_setup", return_value=True),
        patch(
            "homeassistant.components.bluetooth.async_setup_entry", return_value=True
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.onboarding.async_is_onboarded",
            return_value=False,
        ) as mock_onboarding,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_ADAPTER: "hci0", CONF_DETAILS: details1},
        )
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_ADAPTER: "hci1", CONF_DETAILS: details2},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ACME Unknown (00:00:00:00:00:01)"
    assert result["data"] == {}

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "ACME Unknown (00:00:00:00:00:02)"
    assert result2["data"] == {}

    assert len(mock_setup_entry.mock_calls) == 2
    assert len(mock_onboarding.mock_calls) == 2


@pytest.mark.usefixtures("macos_adapter")
async def test_async_step_integration_discovery_during_onboarding(
    hass: HomeAssistant,
) -> None:
    """Test setting up from integration discovery during onboarding."""
    details = AdapterDetails(
        address=DEFAULT_ADDRESS,
        sw_version="1.23.5",
        hw_version="1.2.3",
        manufacturer="ACME",
    )

    with (
        patch("homeassistant.components.bluetooth.async_setup", return_value=True),
        patch(
            "homeassistant.components.bluetooth.async_setup_entry", return_value=True
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.onboarding.async_is_onboarded",
            return_value=False,
        ) as mock_onboarding,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_ADAPTER: "Core Bluetooth", CONF_DETAILS: details},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ACME Unknown (Core Bluetooth)"
    assert result["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_onboarding.mock_calls) == 1


async def test_async_step_integration_discovery_already_exists(
    hass: HomeAssistant,
) -> None:
    """Test setting up from integration discovery when an entry already exists."""
    details = AdapterDetails(
        address="00:00:00:00:00:01",
        sw_version="1.23.5",
        hw_version="1.2.3",
        manufacturer="ACME",
    )

    entry = MockConfigEntry(domain=DOMAIN, unique_id="00:00:00:00:00:01")
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_ADAPTER: "hci0", CONF_DETAILS: details},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures(
    "one_adapter", "mock_bleak_scanner_start", "mock_bluetooth_adapters"
)
async def test_options_flow_linux(hass: HomeAssistant) -> None:
    """Test options on Linux."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={},
        unique_id="00:00:00:00:00:01",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_PASSIVE: True,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PASSIVE] is True

    # Verify we can change it to False

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_PASSIVE: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PASSIVE] is False
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures(
    "macos_adapter", "mock_bleak_scanner_start", "mock_bluetooth_adapters"
)
async def test_options_flow_disabled_macos(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test options are disabled on MacOS."""
    await async_setup_component(hass, "config", {})
    entry = MockConfigEntry(
        domain=DOMAIN, data={}, options={}, unique_id=DEFAULT_ADDRESS
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/get",
            "domain": "bluetooth",
        }
    )
    response = await ws_client.receive_json()
    assert response["result"][0]["supports_options"] is False
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures(
    "one_adapter", "mock_bleak_scanner_start", "mock_bluetooth_adapters"
)
async def test_options_flow_enabled_linux(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test options are enabled on Linux."""
    await async_setup_component(hass, "config", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={},
        unique_id="00:00:00:00:00:01",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/get",
            "domain": "bluetooth",
        }
    )
    response = await ws_client.receive_json()
    assert response["result"][0]["supports_options"] is True
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("one_adapter")
async def test_async_step_user_linux_adapter_is_ignored(hass: HomeAssistant) -> None:
    """Test we give a hint that the adapter is ignored."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="00:00:00:00:00:01",
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_adapters"
    assert result["description_placeholders"] == {"ignored_adapters": "1"}
