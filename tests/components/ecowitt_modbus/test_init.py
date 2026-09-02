"""Test setting a config entry up, and what happens when it fails."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.ecowitt_modbus.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import ALL_MODELS, WN90LP_CASE, ModelCase

from tests.common import MockConfigEntry, async_fire_time_changed

# The coordinator's SCAN_INTERVAL, kept in sync manually rather than imported
# so a change to it is a visible diff here, not a silent test speed-up.
SCAN_INTERVAL = timedelta(seconds=30)

EVERY_MODEL = pytest.mark.parametrize(
    "model_case", ALL_MODELS, ids=lambda case: case.name, indirect=True
)


@EVERY_MODEL
async def test_setup_and_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a config entry sets up and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


@EVERY_MODEL
async def test_device_registry_entry(
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
    model_case: ModelCase,
) -> None:
    """Test the sensor array is registered with what the model reports.

    Only the WN90LP has a serial number and only the WN69LP has a firmware
    version, so this pins that each model contributes what it actually has
    rather than an empty field or a value borrowed from the other.
    """
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, model_case.unique_id), init_integration.entry_id
    )

    assert device is not None
    assert device.manufacturer == "Ecowitt"
    assert device.model == model_case.name
    assert device.serial_number == model_case.serial_number
    assert device.sw_version == model_case.sw_version


@EVERY_MODEL
async def test_a_silent_device_retries_and_recovers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_unit: MockModbusUnit,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Test a device that doesn't answer at setup is retried, not given up on."""
    mock_config_entry.add_to_hass(hass)
    mock_unit.fail_requests(ModbusTimeoutError("no answer"))

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    mock_unit.fail_requests(None)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED


@EVERY_MODEL
async def test_a_poll_reads_only_the_live_block(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_unit: MockModbusUnit,
    init_integration: MockConfigEntry,
    model_case: ModelCase,
) -> None:
    """Test polling does not touch registers outside the live readings.

    Both devices have addresses a poll must stay away from: the WN90LP's
    330-register history block, and the reserved gap the WN69LP documents
    between its configuration and live blocks. Reading into either wastes
    the link at best and is rejected at worst.
    """
    mock_unit.fail_read(
        model_case.unused_register, ModbusTimeoutError("must not be read")
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{model_case.unique_id}_temperature"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "26.2"


@EVERY_MODEL
async def test_link_settings_conflict_is_translated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a clash with another entry on the same gateway is a clean error.

    ``async_get_unit`` raises when the endpoint is already held with
    incompatible framing. That has to surface as a translated config-entry
    error, not fall through to the generic handler.
    """
    mock_config_entry.add_to_hass(hass)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "homeassistant.components.ecowitt_modbus.async_get_unit",
            MagicMock(side_effect=HomeAssistantError("already in use")),
        )
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert "already in use" in str(mock_config_entry.reason)


@EVERY_MODEL
@pytest.mark.usefixtures("mock_get_unit")
async def test_setup_is_rejected_when_another_device_answers(
    hass: HomeAssistant,
    mock_unit: MockModbusUnit,
    mock_config_entry: MockConfigEntry,
    model_case: ModelCase,
) -> None:
    """Test an entry pointed at something else never registers entities.

    The address in an entry can come to point elsewhere -- a reconfigured
    gateway, a reused device address. Setup must fail rather than adopt
    whatever now answers.
    """
    mock_config_entry.add_to_hass(hass)
    for address, value in model_case.impostor_registers.items():
        mock_unit.holding[address] = value

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


class TestSerialNumberRevalidation:
    """A WN90LP swapped for a different WN90LP while Home Assistant runs.

    Only applies to models that report a serial number. The WN69LP reports
    none, so there is nothing to revalidate and no test to write -- that
    limitation is asserted in ``test_wn69lp_has_no_identity_to_revalidate``.
    """

    @pytest.fixture
    def register_image(self) -> dict[int, int]:
        """A WN90LP reporting a different device ID than the entry expects."""
        image = dict(WN90LP_CASE.registers)
        image[0x163] = 0x0000
        image[0x164] = 0x0001
        return image

    @pytest.mark.usefixtures("mock_get_unit")
    async def test_setup_is_rejected(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test the swap is caught before any entity is created."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_a_swap_after_setup_takes_entities_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_unit: MockModbusUnit,
    init_integration: MockConfigEntry,
) -> None:
    """Test a WN90LP replaced mid-run stops publishing under the old entities.

    Distinct from setup-time rejection: the entry is already loaded, so the
    coordinator -- not ``async_setup_entry`` -- is what has to notice. The
    entry stays loaded because this surfaces as a failed update, the same
    way a dropped connection does.
    """
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{WN90LP_CASE.unique_id}_temperature"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "26.2"

    mock_unit.holding[0x163] = 0x0000
    mock_unit.holding[0x164] = 0x0001

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert init_integration.state is ConfigEntryState.LOADED


@pytest.mark.parametrize("model_case", [ALL_MODELS[1]], ids=["WN69LP"], indirect=True)
async def test_wn69lp_has_no_identity_to_revalidate(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
    model_case: ModelCase,
) -> None:
    """Test a WN69LP swap goes unnoticed, because the device allows nothing else.

    This pins a documented limitation rather than desired behaviour: the
    WN69LP reports no serial number, so a different WN69LP at the same
    address is indistinguishable and its readings are published under the
    original entry. If the device ever gains an identity register, this test
    should start failing.
    """
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{model_case.unique_id}_temperature"
    )
    assert entity_id is not None

    # A different physical sensor, reporting a different temperature.
    mock_connection.for_unit(model_case.unit_id).holding[0x182] = 500

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "10.0"


@EVERY_MODEL
async def test_entities_go_unavailable_when_the_link_drops(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_unit: MockModbusUnit,
    init_integration: MockConfigEntry,
    model_case: ModelCase,
) -> None:
    """Test a silent device takes its entities unavailable, then recovers."""
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{model_case.unique_id}_temperature"
    )
    assert entity_id is not None

    mock_unit.fail_requests(ModbusTimeoutError("no answer"))
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # Recovery must not need a reload: every request connects first.
    mock_unit.fail_requests(None)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "26.2"
    assert init_integration.state is ConfigEntryState.LOADED
