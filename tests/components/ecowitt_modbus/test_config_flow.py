"""Test the Ecowitt Modbus config flow."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, _patch, patch

from modbus_connection import ModbusTcpParams, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.ecowitt_modbus.const import (
    CONF_UNIT_ID,
    DOMAIN,
    MAX_UNIT_ID,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from . import ALL_MODELS, MOCK_HOST, WN69LP_CASE, WS90_CASE, ModelCase

from tests.common import MockConfigEntry

TARGET = "homeassistant.components.ecowitt_modbus.config_flow.async_get_temporary_unit"

EVERY_MODEL = pytest.mark.parametrize(
    "model_case", ALL_MODELS, ids=lambda case: case.name, indirect=True
)


def _serving(unit_id: int, image: dict[int, int]) -> _patch:
    """Patch the temporary unit onto a device answering with *image*."""
    connection = MockModbusConnection()
    connection.for_unit(unit_id).load_raw({"holding": dict(image)})

    @asynccontextmanager
    async def _get_unit(
        hass: HomeAssistant, params: ModbusTcpParams, requested: int
    ) -> AsyncIterator[MockModbusUnit]:
        yield connection.for_unit(requested)

    return patch(TARGET, side_effect=_get_unit)


def _raising(error: Exception) -> _patch:
    """Patch the temporary unit so acquiring it fails."""
    return patch(TARGET, side_effect=error)


async def _pick_model(hass: HomeAssistant, model_case: ModelCase) -> str:
    """Start a flow and get through the model-selection step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MODEL: model_case.slug}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"
    assert result["errors"] == {}
    return str(result["flow_id"])


@EVERY_MODEL
@pytest.mark.usefixtures("mock_temporary_unit")
async def test_full_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, model_case: ModelCase
) -> None:
    """Test picking a model and address creates the entry it should."""
    flow_id = await _pick_model(hass, model_case)

    result = await hass.config_entries.flow.async_configure(
        flow_id, model_case.user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{model_case.name} ({MOCK_HOST})"
    assert result["data"] == model_case.entry_data
    assert result["result"].unique_id == model_case.unique_id
    assert len(mock_setup_entry.mock_calls) == 1


@EVERY_MODEL
@pytest.mark.usefixtures("mock_temporary_unit")
async def test_the_address_form_defaults_to_the_models_own_address(
    hass: HomeAssistant, model_case: ModelCase
) -> None:
    """Test each model's factory-default device address is pre-filled.

    The two models ship on different addresses, so a shared default would
    be wrong for one of them.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MODEL: model_case.slug}
    )

    schema = result["data_schema"].schema
    unit_id = next(key for key in schema if key == CONF_UNIT_ID)
    assert unit_id.default() == model_case.unit_id


@EVERY_MODEL
@pytest.mark.usefixtures("mock_temporary_unit")
async def test_the_address_form_rejects_reserved_addresses(
    hass: HomeAssistant, model_case: ModelCase
) -> None:
    """Test the device-address box stops at the end of the RTU range.

    Addresses 248-252 fit in the sensors' own address register but cannot be
    reached over the wire, so offering them would only produce a failed probe.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MODEL: model_case.slug}
    )

    schema = result["data_schema"].schema
    validator = next(schema[key] for key in schema if key == CONF_UNIT_ID)
    selector = validator.validators[0]
    assert selector.config["max"] == MAX_UNIT_ID


@EVERY_MODEL
@pytest.mark.usefixtures("mock_temporary_unit")
async def test_errors_show_on_the_form_and_the_flow_still_completes(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    model_case: ModelCase,
) -> None:
    """Test every failure mode recovers without restarting the flow."""
    failures: list[tuple[Callable[[], _patch], str]] = [
        (lambda: _raising(ModbusTimeoutError("no answer")), "cannot_connect"),
        # The device is already held on different link settings.
        (lambda: _raising(HomeAssistantError("in use")), "cannot_connect"),
        (lambda: _raising(RuntimeError("boom")), "unknown"),
    ]

    flow_id = await _pick_model(hass, model_case)
    for failure, expected_error in failures:
        with failure():
            result = await hass.config_entries.flow.async_configure(
                flow_id, model_case.user_input
            )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": expected_error}, expected_error

    # The healthy device the fixture serves is back once the failures lift.
    result = await hass.config_entries.flow.async_configure(
        flow_id, model_case.user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == model_case.unique_id


@EVERY_MODEL
@pytest.mark.usefixtures("mock_temporary_unit")
async def test_the_wrong_model_at_the_address_is_reported_as_such(
    hass: HomeAssistant, model_case: ModelCase
) -> None:
    """Test a device that answers but is not the chosen model is distinguished.

    "Something else is here" is a different problem from "nothing answered",
    and the user needs to be told which one it is.
    """
    impostor = dict(model_case.registers) | model_case.impostor_registers
    flow_id = await _pick_model(hass, model_case)

    with _serving(model_case.unit_id, impostor):
        result = await hass.config_entries.flow.async_configure(
            flow_id, model_case.user_input
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "wrong_model"}


@EVERY_MODEL
@pytest.mark.usefixtures("mock_temporary_unit")
async def test_the_same_device_cannot_be_added_twice(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    model_case: ModelCase,
) -> None:
    """Test re-adding a configured sensor array aborts."""
    mock_config_entry.add_to_hass(hass)

    flow_id = await _pick_model(hass, model_case)
    result = await hass.config_entries.flow.async_configure(
        flow_id, model_case.user_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_temporary_unit")
async def test_a_ws90_is_recognised_at_a_new_address(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a WS90's serial number identifies it wherever it is reached.

    Moving a WS90 to another gateway must not let it be added a second time,
    which is the whole point of keying the entry on the device ID.
    """
    mock_config_entry.add_to_hass(hass)

    flow_id = await _pick_model(hass, WS90_CASE)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**WS90_CASE.user_input, CONF_HOST: "192.168.1.200"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("model_case", [WN69LP_CASE], ids=["WN69LP"], indirect=True)
@pytest.mark.usefixtures("mock_temporary_unit")
async def test_a_wn69lp_at_a_new_address_looks_like_a_new_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the flip side of the WN69LP reporting no identity.

    Nothing distinguishes the same sensor at a new address from a second
    sensor, so it is added again. This pins a documented limitation, not a
    desirable outcome; moving one is what the reconfigure flow is for.
    """
    mock_config_entry.add_to_hass(hass)

    flow_id = await _pick_model(hass, WN69LP_CASE)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**WN69LP_CASE.user_input, CONF_HOST: "192.168.1.200"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id != WN69LP_CASE.unique_id


class TestReconfigure:
    """Moving a configured sensor array to a new address."""

    @EVERY_MODEL
    @pytest.mark.usefixtures("mock_temporary_unit")
    async def test_the_form_is_seeded_with_the_current_settings(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        model_case: ModelCase,
    ) -> None:
        """Test the user amends what is there instead of retyping it."""
        mock_config_entry.add_to_hass(hass)

        result = await mock_config_entry.start_reconfigure_flow(hass)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
        schema = result["data_schema"].schema
        defaults = {str(key): key.default() for key in schema}
        assert defaults[CONF_HOST] == MOCK_HOST
        assert defaults[CONF_PORT] == 502
        assert defaults[CONF_UNIT_ID] == model_case.unit_id

    @EVERY_MODEL
    @pytest.mark.usefixtures("mock_temporary_unit")
    async def test_an_address_holding_a_different_model_is_refused(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        model_case: ModelCase,
    ) -> None:
        """Test the entry is not repointed at something that is not this model.

        The model is fixed for the life of an entry, so an address where the
        other model answers is not a valid destination.
        """
        mock_config_entry.add_to_hass(hass)
        impostor = dict(model_case.registers) | model_case.impostor_registers

        result = await mock_config_entry.start_reconfigure_flow(hass)
        with _serving(model_case.unit_id, impostor):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {**model_case.user_input, CONF_HOST: "192.168.1.200"},
            )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "wrong_model"}
        assert mock_config_entry.data[CONF_HOST] == MOCK_HOST

    @EVERY_MODEL
    @pytest.mark.usefixtures("mock_temporary_unit")
    async def test_an_unexpected_error_leaves_the_entry_alone(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        model_case: ModelCase,
    ) -> None:
        """Test a bug in the probe path does not lose the working settings."""
        mock_config_entry.add_to_hass(hass)

        result = await mock_config_entry.start_reconfigure_flow(hass)
        with _raising(RuntimeError("boom")):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {**model_case.user_input, CONF_HOST: "192.168.1.200"},
            )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}
        assert mock_config_entry.data[CONF_HOST] == MOCK_HOST

    @EVERY_MODEL
    @pytest.mark.usefixtures("mock_temporary_unit", "mock_setup_entry")
    async def test_a_new_address_is_saved(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        model_case: ModelCase,
    ) -> None:
        """Test both models can be moved to a new gateway."""
        mock_config_entry.add_to_hass(hass)

        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**model_case.user_input, CONF_HOST: "192.168.1.200"},
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"
        # The model is not re-asked, so it has to survive the round trip.
        assert mock_config_entry.data[CONF_MODEL] == model_case.name

    @EVERY_MODEL
    @pytest.mark.usefixtures("mock_temporary_unit")
    async def test_an_address_with_nothing_at_it_is_refused(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        model_case: ModelCase,
    ) -> None:
        """Test the entry is not repointed somewhere that does not answer."""
        mock_config_entry.add_to_hass(hass)

        result = await mock_config_entry.start_reconfigure_flow(hass)
        with _raising(ModbusTimeoutError("no answer")):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {**model_case.user_input, CONF_HOST: "192.168.1.200"},
            )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
        assert mock_config_entry.data[CONF_HOST] == MOCK_HOST

    @pytest.mark.usefixtures("mock_temporary_unit")
    async def test_a_ws90_entry_will_not_adopt_a_different_ws90(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test the serial number is checked before repointing an entry.

        Otherwise the new sensor would silently inherit the old one's
        history.
        """
        mock_config_entry.add_to_hass(hass)
        other = dict(WS90_CASE.registers) | {0x163: 0x0000, 0x164: 0x0001}

        result = await mock_config_entry.start_reconfigure_flow(hass)
        with _serving(WS90_CASE.unit_id, other):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {**WS90_CASE.user_input, CONF_HOST: "192.168.1.200"},
            )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "another_device"
        assert mock_config_entry.data[CONF_HOST] == MOCK_HOST

    @pytest.mark.parametrize("model_case", [WN69LP_CASE], ids=["WN69LP"], indirect=True)
    @pytest.mark.usefixtures("mock_temporary_unit")
    async def test_a_wn69lp_will_not_move_onto_another_entrys_address(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test the one collision a model without an identity can still catch.

        Its serial number cannot be checked, but two entries polling the
        same address can be, and would fight over the same device.
        """
        mock_config_entry.add_to_hass(hass)
        neighbour = MockConfigEntry(
            domain=DOMAIN,
            unique_id="wn69lp_192.168.1.200_502_36",
            data={**WN69LP_CASE.entry_data, CONF_HOST: "192.168.1.200"},
        )
        neighbour.add_to_hass(hass)

        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**WN69LP_CASE.user_input, CONF_HOST: "192.168.1.200"},
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
        assert mock_config_entry.data[CONF_HOST] == MOCK_HOST

    @pytest.mark.parametrize("model_case", [WN69LP_CASE], ids=["WN69LP"], indirect=True)
    @pytest.mark.usefixtures("mock_temporary_unit", "mock_setup_entry")
    async def test_a_wn69lp_keeps_its_original_unique_id(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test moving an identity-less sensor does not orphan its entities.

        Its unique ID was derived from the address it was first found at.
        Recomputing that on a move would change the ID every entity is
        keyed under, losing all of their history.
        """
        mock_config_entry.add_to_hass(hass)

        result = await mock_config_entry.start_reconfigure_flow(hass)
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**WN69LP_CASE.user_input, CONF_HOST: "192.168.1.200"},
        )
        await hass.async_block_till_done()

        assert mock_config_entry.unique_id == WN69LP_CASE.unique_id
