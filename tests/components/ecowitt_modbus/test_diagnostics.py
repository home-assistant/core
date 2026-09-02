"""Test Ecowitt Modbus diagnostics."""

import json

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import ALL_MODELS, MOCK_HOST, ModelCase

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
async def test_identifying_details_are_redacted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    model_case: ModelCase,
) -> None:
    """Test a shared diagnostics dump gives away neither address nor hardware.

    Snapshots would catch a change to this, but only if someone reads them.
    An explicit assertion says which fields are sensitive and, just as
    importantly, that the same value does not survive somewhere else: a
    WS90's serial number is also its raw ``device_id`` register and its
    config entry's unique ID, and a WN69LP's unique ID embeds its host.
    """
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert result["entry"]["data"][CONF_HOST] == "**REDACTED**"
    assert result["entry"]["unique_id"] == "**REDACTED**"

    if model_case.serial_number is not None:
        assert result["device"]["serial_number"] == "**REDACTED**"
        assert result["configuration"]["device_id"] == "**REDACTED**"

    # Belt and braces: nothing anywhere in the dump still carries either.
    dumped = json.dumps(result)
    assert MOCK_HOST not in dumped
    if model_case.serial_number is not None:
        assert model_case.serial_number not in dumped
        # The same value unformatted, as the identity register holds it.
        assert str(int(model_case.serial_number, 16)) not in dumped


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
