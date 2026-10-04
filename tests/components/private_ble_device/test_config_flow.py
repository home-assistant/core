"""Tests for private bluetooth device config flow."""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.private_ble_device import const
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import async_mock_config_entry

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


def assert_form_error(result: FlowResult, key: str, value: str) -> None:
    """Assert that a flow returned a form error."""
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]
    assert result["errors"][key] == value


@pytest.mark.usefixtures("mock_bluetooth_adapters")
async def test_setup_user_no_bluetooth(hass: HomeAssistant) -> None:
    """Test setting up via user interaction when bluetooth is not enabled."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "bluetooth_not_available"


@pytest.mark.usefixtures("enable_bluetooth")
async def test_invalid_irk(hass: HomeAssistant) -> None:
    """Test invalid irk."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"irk": "irk:000000"}
    )
    assert_form_error(result, "irk", "irk_not_valid")


@pytest.mark.usefixtures("enable_bluetooth")
async def test_invalid_irk_base64(hass: HomeAssistant) -> None:
    """Test invalid irk."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"irk": "Ucredacted4T8n!!ZZZ=="}
    )
    assert_form_error(result, "irk", "irk_not_valid")


@pytest.mark.usefixtures("enable_bluetooth")
async def test_invalid_irk_hex(hass: HomeAssistant) -> None:
    """Test invalid irk."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"irk": "irk:abcdefghi"}
    )
    assert_form_error(result, "irk", "irk_not_valid")


@pytest.mark.usefixtures("enable_bluetooth")
async def test_irk_not_found(hass: HomeAssistant) -> None:
    """Test irk not found."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"irk": "irk:00000000000000000000000000000000"},
    )
    assert_form_error(result, "irk", "irk_not_found")


@pytest.mark.usefixtures("enable_bluetooth")
async def test_flow_works(hass: HomeAssistant) -> None:
    """Test config flow works."""

    inject_bluetooth_service_info(
        hass,
        BluetoothServiceInfo(
            name="Test Test Test",
            address="40:01:02:0a:c4:a6",
            rssi=-63,
            service_data={},
            manufacturer_data={},
            service_uuids=[],
            source="local",
        ),
    )

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    # Check you can finish the flow
    with patch(
        "homeassistant.components.private_ble_device.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"irk": "irk:00000000000000000000000000000000"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Test Test"
    assert result["data"] == {"irk": "00000000000000000000000000000000"}
    assert result["result"].unique_id == "00000000000000000000000000000000"


@pytest.mark.usefixtures("enable_bluetooth")
async def test_flow_works_by_base64(hass: HomeAssistant) -> None:
    """Test config flow works."""

    inject_bluetooth_service_info(
        hass,
        BluetoothServiceInfo(
            name="Test Test Test",
            address="40:01:02:0a:c4:a6",
            rssi=-63,
            service_data={},
            manufacturer_data={},
            service_uuids=[],
            source="local",
        ),
    )

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    # Check you can finish the flow
    with patch(
        "homeassistant.components.private_ble_device.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"irk": "AAAAAAAAAAAAAAAAAAAAAA=="},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Test Test"
    assert result["data"] == {"irk": "00000000000000000000000000000000"}
    assert result["result"].unique_id == "00000000000000000000000000000000"


OLD_IRK = "11111111111111111111111111111111"
NEW_IRK = "00000000000000000000000000000000"  # resolves 40:01:02:0a:c4:a6


def _inject_new_irk_device(hass: HomeAssistant) -> None:
    inject_bluetooth_service_info(
        hass,
        BluetoothServiceInfo(
            name="Test Test Test",
            address="40:01:02:0a:c4:a6",
            rssi=-63,
            service_data={},
            manufacturer_data={},
            service_uuids=[],
            source="local",
        ),
    )


@pytest.mark.usefixtures("enable_bluetooth")
async def test_reconfigure_replaces_irk(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a new IRK keeps the entities and device, only their ids move."""
    await async_mock_config_entry(hass, OLD_IRK)
    entry = hass.config_entries.async_get_entry(OLD_IRK)
    before = {
        e.entity_id: e.unique_id
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    }
    assert before and all(OLD_IRK in uid for uid in before.values())
    device = device_registry.async_get_device_by_identifier(
        (const.DOMAIN, OLD_IRK), entry.entry_id
    )
    # Another integration attached to the same identifier stays as it is.
    other = MockConfigEntry(domain="other")
    other.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other.entry_id, identifiers={(const.DOMAIN, OLD_IRK)}
    )

    _inject_new_irk_device(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"irk": f"irk:{NEW_IRK}"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {"irk": NEW_IRK}
    assert entry.unique_id == NEW_IRK
    assert entry.state is ConfigEntryState.LOADED
    after = {
        e.entity_id: e.unique_id
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    }
    assert after == {
        entity_id: uid.replace(OLD_IRK, NEW_IRK) for entity_id, uid in before.items()
    }
    assert device_registry.async_get(device.id).identifiers == {(const.DOMAIN, NEW_IRK)}
    assert device_registry.async_get(other_device.id).identifiers == {
        (const.DOMAIN, OLD_IRK)
    }


@pytest.mark.usefixtures("enable_bluetooth")
@pytest.mark.parametrize(
    ("irk", "error"),
    [
        ("irk:000000", "irk_not_valid"),
        ("irk:22222222222222222222222222222222", "irk_not_found"),
    ],
)
async def test_reconfigure_errors(hass: HomeAssistant, irk: str, error: str) -> None:
    """Test a bad or unseen IRK is refused and the entry keeps its own."""
    await async_mock_config_entry(hass, OLD_IRK)
    entry = hass.config_entries.async_get_entry(OLD_IRK)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"irk": irk}
    )
    assert_form_error(result, "irk", error)
    assert entry.data == {"irk": OLD_IRK}


@pytest.mark.usefixtures("enable_bluetooth")
async def test_reconfigure_to_an_irk_in_use(hass: HomeAssistant) -> None:
    """Test an IRK another entry already tracks is refused."""
    await async_mock_config_entry(hass, OLD_IRK)
    await async_mock_config_entry(hass, NEW_IRK)
    entry = hass.config_entries.async_get_entry(OLD_IRK)

    _inject_new_irk_device(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"irk": NEW_IRK}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {"irk": OLD_IRK}


@pytest.mark.usefixtures("enable_bluetooth")
async def test_reconfigure_stops_when_the_entry_will_not_unload(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test nothing moves when the entry cannot be unloaded."""
    await async_mock_config_entry(hass, OLD_IRK)
    entry = hass.config_entries.async_get_entry(OLD_IRK)
    unique_id = entry.unique_id
    before = {
        e.entity_id: e.unique_id
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    }

    _inject_new_irk_device(hass)
    result = await entry.start_reconfigure_flow(hass)
    with patch.object(hass.config_entries, "async_unload", return_value=False):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"irk": NEW_IRK}
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unload_failed"
    assert entry.data == {"irk": OLD_IRK}
    assert entry.unique_id == unique_id
    assert {
        e.entity_id: e.unique_id
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    } == before


@pytest.mark.usefixtures("mock_bluetooth_adapters")
async def test_reconfigure_no_bluetooth(hass: HomeAssistant) -> None:
    """Test reconfiguring is refused when bluetooth is not enabled."""
    entry = MockConfigEntry(domain=const.DOMAIN, data={"irk": OLD_IRK})
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "bluetooth_not_available"
    assert entry.data == {"irk": OLD_IRK}


@pytest.mark.usefixtures("enable_bluetooth")
async def test_reconfigure_two_entries_to_the_same_irk_at_once(
    hass: HomeAssistant,
) -> None:
    """Test a second flow moving an entry to an IRK already being moved to aborts."""
    other_irk = "22222222222222222222222222222222"
    await async_mock_config_entry(hass, OLD_IRK)
    await async_mock_config_entry(hass, other_irk)
    first = hass.config_entries.async_get_entry(OLD_IRK)
    second = hass.config_entries.async_get_entry(other_irk)
    _inject_new_irk_device(hass)

    unloading = asyncio.Event()
    release = asyncio.Event()
    real_unload = hass.config_entries.async_unload

    async def slow_unload(entry_id: str, **kwargs: bool) -> bool:
        # Only the first flow's unload is held; anything after runs through.
        if not unloading.is_set():
            unloading.set()
            await release.wait()
        return await real_unload(entry_id, **kwargs)

    flow_1 = await first.start_reconfigure_flow(hass)
    flow_2 = await second.start_reconfigure_flow(hass)
    with patch.object(hass.config_entries, "async_unload", side_effect=slow_unload):
        # The first flow stops part way, while its entry unloads.
        task = hass.async_create_task(
            hass.config_entries.flow.async_configure(
                flow_1["flow_id"], user_input={"irk": NEW_IRK}
            )
        )
        await unloading.wait()
        result_2 = await hass.config_entries.flow.async_configure(
            flow_2["flow_id"], user_input={"irk": NEW_IRK}
        )
        release.set()
        result_1 = await task
    await hass.async_block_till_done()

    assert result_2["type"] is FlowResultType.ABORT
    assert result_2["reason"] == "already_in_progress"
    assert second.data == {"irk": other_irk}
    assert result_1["reason"] == "reconfigure_successful"
    assert first.data == {"irk": NEW_IRK}


@pytest.mark.usefixtures("enable_bluetooth")
async def test_reconfigure_to_the_irk_it_already_has(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test giving a device its own IRK changes nothing and keeps it loaded."""
    await async_mock_config_entry(hass, NEW_IRK)
    entry = hass.config_entries.async_get_entry(NEW_IRK)
    before = {
        e.entity_id: e.unique_id
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    }

    _inject_new_irk_device(hass)
    result = await entry.start_reconfigure_flow(hass)
    with patch.object(
        hass.config_entries, "async_unload", wraps=hass.config_entries.async_unload
    ) as unload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"irk": NEW_IRK}
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert unload.call_count == 0
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data == {"irk": NEW_IRK}
    assert {
        e.entity_id: e.unique_id
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    } == before
