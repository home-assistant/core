"""Test the BLE Battery Management System integration config flow."""

from typing import Final

from aiobmsble.test_data import bms_advertisements
from bleak.backends.scanner import AdvertisementData
from home_assistant_bluetooth import BluetoothServiceInfoBleak
import pytest
from voluptuous import Schema

from homeassistant.components.bms_ble.const import (
    BINARY_SENSORS,
    DOMAIN,
    LINK_SENSORS,
    SENSORS,
)
from homeassistant.config_entries import (
    SOURCE_BLUETOOTH,
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from .conftest import mock_config, mock_devinfo_min, mock_update_full, mock_update_min

from tests.common import MockConfigEntry
from tests.components.bluetooth import (
    generate_ble_device,
    inject_bluetooth_service_info_bleak,
)


@pytest.fixture(
    name="advertisement",
    params=bms_advertisements(),
    ids=lambda param: param[2],
)
def bms_adv(request: pytest.FixtureRequest) -> BluetoothServiceInfoBleak:
    """Return faulty response frame."""
    dev: Final[AdvertisementData] = request.param[0]
    address: Final[str] = request.param[1]
    return BluetoothServiceInfoBleak(
        name=str(dev.local_name),
        address=address,
        device=generate_ble_device(
            address=address, name=dev.local_name, details=request.param[2]
        ),
        rssi=dev.rssi,
        service_uuids=dev.service_uuids,
        manufacturer_data=dev.manufacturer_data,
        service_data=dev.service_data,
        advertisement=dev,
        source=SOURCE_BLUETOOTH,
        connectable=True,
        time=0,
        tx_power=dev.tx_power,
    )


@pytest.mark.usefixtures("enable_bluetooth")
async def test_bluetooth_discovery(
    hass: HomeAssistant, advertisement: BluetoothServiceInfoBleak
) -> None:
    """Test bluetooth device discovery."""

    inject_bluetooth_service_info_bleak(hass, advertisement)
    await hass.async_block_till_done(wait_background_tasks=True)

    flowresults: list[ConfigFlowResult] = (
        hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    )
    assert len(flowresults) == 1, (
        f"Expected one flow result for {advertisement}, check manifest.json!"
    )
    result: ConfigFlowResult = flowresults[0]
    assert result.get("step_id") == "bluetooth_confirm"
    assert result.get("context", {}).get("unique_id") == advertisement.address

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"not": "empty"}
    )
    await hass.async_block_till_done()
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert (
        result.get("title") == advertisement.name or advertisement.address
    )  # address is used as name by Bleak if name is not available

    # BluetoothServiceInfoBleak contains BMS type as details to BLEDevice, see bms_advertisement
    assert (
        hass.config_entries.async_entries()[1].data["type"]
        == f"aiobmsble.bms.{advertisement.device.details}"
    )


@pytest.mark.parametrize(
    ("sensor_set", "sensor_count"),
    [
        (
            "min",
            (
                min(BINARY_SENSORS, 1),
                SENSORS - 3,
                min(BINARY_SENSORS, 1) + (SENSORS - 1) + LINK_SENSORS,
            ),
        ),
        (
            "full",
            (
                max(BINARY_SENSORS - 4, 0),
                SENSORS - 2,  # link sensors are disabled by default
                BINARY_SENSORS + SENSORS + LINK_SENSORS,
            ),
        ),
    ],
    ids=["minimal", "full"],
)
@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_device_setup(
    monkeypatch: pytest.MonkeyPatch,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
    sensor_set: str,
    sensor_count: tuple[int, int, int],
) -> None:
    """Test discovery via bluetooth with a valid device."""

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=bt_discovery,
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "bluetooth_confirm"
    assert result.get("description_placeholders") == {
        "name": "SmartBat-B12345",
        "id": ":cc:cc:cc",
        "model": "OGT BMS",
    }

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    monkeypatch.setattr(
        "aiobmsble.bms.ogt_bms.BMS.async_update",
        mock_update_full if sensor_set == "full" else mock_update_min,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"not": "empty"}
    )
    await hass.async_block_till_done()
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "SmartBat-B12345"

    result_detail: ConfigEntry | None = result.get("result")
    assert result_detail is not None
    assert result_detail.unique_id == "cc:cc:cc:cc:cc:cc"

    entities: er.EntityRegistryItems = er.async_get(hass).entities
    # check number of sensors minus the ones disabled by default
    assert len(hass.states.async_all(["binary_sensor"])) == sensor_count[0]
    assert len(hass.states.async_all(["sensor"])) == sensor_count[1]
    # check overall entities (including disabled sensors)
    assert len(entities) == sensor_count[2]

    # check correct unique_id format of all sensor entries
    for entry in entities.get_entries_for_config_entry_id(result_detail.entry_id):
        assert entry.unique_id.startswith(f"{DOMAIN}-cc:cc:cc:cc:cc:cc-")


@pytest.mark.usefixtures("enable_bluetooth")
async def test_device_not_supported(
    bt_discovery_notsupported: BluetoothServiceInfoBleak, hass: HomeAssistant
) -> None:
    """Test discovery via bluetooth with a invalid device."""

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=bt_discovery_notsupported,
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "not_supported"


@pytest.mark.usefixtures("enable_bluetooth")
async def test_already_configured(bms_fixture: str, hass: HomeAssistant) -> None:
    """Test that same device cannot be added twice."""

    cfg: MockConfigEntry = mock_config(bms_fixture)
    cfg.add_to_hass(hass)

    await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_ADDRESS: "cc:cc:cc:cc:cc:cc",
            "type": "aiobmsble.bms.ogt_bms",
        },
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_async_setup_entry(
    monkeypatch: pytest.MonkeyPatch,
    bms_fixture: str,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Test async_setup_entry with valid input."""

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    cfg: MockConfigEntry = mock_config(bms=bms_fixture)
    cfg.add_to_hass(hass)

    bms_module: Final[str] = f"aiobmsble.bms.{bms_fixture}"
    monkeypatch.setattr(f"{bms_module}.BMS.device_info", mock_devinfo_min)
    monkeypatch.setattr(f"{bms_module}.BMS.async_update", mock_update_min)

    assert await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    assert cfg in hass.config_entries.async_entries()
    assert cfg.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("enable_bluetooth")
async def test_setup_entry_missing_unique_id(bms_fixture, hass: HomeAssistant) -> None:
    """Test async_setup_entry with missing unique id."""

    cfg: MockConfigEntry = mock_config(bms=bms_fixture, unique_id=None)
    cfg.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(cfg.entry_id)

    assert cfg in hass.config_entries.async_entries()
    assert cfg.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.usefixtures(
    "enable_bluetooth", "patch_default_bleak_client", "patch_entity_enabled_default"
)
async def test_user_setup(
    monkeypatch: pytest.MonkeyPatch,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Check config flow for user adding previously discovered device."""

    monkeypatch.setattr(
        "aiobmsble.bms.ogt_bms.BMS.async_update",
        mock_update_full,
    )

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") is None

    data_schema: Final[Schema | None] = result.get("data_schema")
    assert data_schema is not None
    assert data_schema.schema.get(CONF_ADDRESS).serialize() == {
        "selector": {
            "select": {
                "options": [
                    {
                        "value": "cc:cc:cc:cc:cc:cc",
                        "label": "SmartBat-B12345 (cc:cc:cc:cc:cc:cc) - OGT BMS",
                    }
                ],
                "multiple": False,
                "custom_value": False,
                "sort": False,
            }
        }
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ADDRESS: "cc:cc:cc:cc:cc:cc"}
    )

    await hass.async_block_till_done()
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "SmartBat-B12345"

    result_detail: ConfigEntry | None = result.get("result")
    assert result_detail is not None
    assert result_detail.unique_id == "cc:cc:cc:cc:cc:cc"
    assert (
        len(hass.states.async_all(["sensor", "binary_sensor"]))
        == BINARY_SENSORS + SENSORS + LINK_SENSORS
    )


@pytest.mark.usefixtures("enable_bluetooth")
async def test_user_setup_invalid(
    bt_discovery_notsupported: BluetoothServiceInfoBleak, hass: HomeAssistant
) -> None:
    """Check config flow for user adding previously discovered invalid device."""

    inject_bluetooth_service_info_bleak(hass, bt_discovery_notsupported)
    result: Final[ConfigFlowResult] = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.ABORT


@pytest.mark.usefixtures("enable_bluetooth")
async def test_user_setup_double_configure(
    monkeypatch: pytest.MonkeyPatch,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Check config flow for user adding previously already added device."""

    def patch_async_current_ids(_self, include_ignore: bool = True) -> set[str | None]:
        return {None if include_ignore else "cc:cc:cc:cc:cc:cc"}

    monkeypatch.setattr(
        "homeassistant.components.bms_ble.config_flow.ConfigFlow._async_current_ids",
        patch_async_current_ids,
    )

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.ABORT
