"""Test Ecowitt Modbus diagnostics."""

import json

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import ALL_MODELS, MOCK_HOST, WS90_CASE, ModelCase

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

EVERY_MODEL = pytest.mark.parametrize(
    "model_case", ALL_MODELS, ids=lambda case: case.name, indirect=True
)


@EVERY_MODEL
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostics match their snapshot for each model."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )


@EVERY_MODEL
async def test_the_address_is_redacted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test a shared diagnostics dump does not give away where the sensor is.

    Snapshots would catch a change to this, but only if someone reads them.
    The unique ID matters as much as the host field: a model with no serial
    number has its host embedded in it.
    """
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert result["entry"]["data"][CONF_HOST] == "**REDACTED**"
    assert result["entry"]["unique_id"] == "**REDACTED**"
    assert MOCK_HOST not in json.dumps(result)


@pytest.mark.parametrize("model_case", [WS90_CASE], ids=["WS90"], indirect=True)
async def test_the_serial_number_is_redacted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    model_case: ModelCase,
) -> None:
    """Test the hardware identity does not survive anywhere in the dump.

    Only the WS90 has one. It appears three times over -- as
    ``serial_number``, as the raw ``device_id`` register it is formatted
    from, and as the config entry's unique ID -- so redacting the obvious
    field alone would not be enough.
    """
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert result["device"]["serial_number"] == "**REDACTED**"
    assert result["configuration"]["device_id"] == "**REDACTED**"

    serial = model_case.serial_number
    assert serial is not None
    dumped = json.dumps(result)
    assert serial not in dumped
    # The same value unformatted, as the identity register holds it.
    assert str(int(serial, 16)) not in dumped


@EVERY_MODEL
async def test_readings_include_values_no_entity_surfaces(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    model_case: ModelCase,
) -> None:
    """Test diagnostics report everything the model decodes.

    Diagnostics exist to explain behaviour the entities cannot, so they are
    driven off the device's own field list rather than the entity list.
    """
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert set(result["readings"]) >= set(model_case.entity_keys) - {"rain_counter"}
    assert result["readings"]["temperature"] == 26.2
    assert result["configuration"]["baud_rate"] is not None
