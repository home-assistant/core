"""Tests for the Ecowitt Modbus integration.

The two models share a config flow, coordinator, and entity layer, but
differ in ways that matter: only the WS90 reports a serial number, and only
the WN69LP needs a second read for its configuration block.

Behaviour that should be identical across models is parametrized over both,
so a change that suits one and breaks the other fails here. Behaviour that
only one model has -- serial-number revalidation, the WN69LP's diagnostic
voltages -- gets its own test naming the model it covers. Each model is
described by a :class:`ModelCase`, so a test can vary by model without
branching on the model name in its body.
"""

from dataclasses import dataclass, field
from typing import Any

from ecowitt_modbus import WN69LP, WS90, EcowittDevice
from ecowitt_modbus.testing import (
    WN69LP_LIVE_EXAMPLE,
    WN69LP_UNIT_ID,
    WS90_LIVE_EXAMPLE,
    WS90_UNIT_ID,
)

from homeassistant.components.ecowitt_modbus.const import CONF_UNIT_ID
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PORT

MOCK_HOST = "192.168.1.100"
MOCK_PORT = 502


@dataclass(frozen=True, kw_only=True)
class ModelCase:
    """One supported model, and what the integration should make of it."""

    model: type[EcowittDevice]
    unit_id: int
    registers: dict[int, int]

    #: The config entry unique ID this model's device should end up with.
    unique_id: str

    #: Serial number reported to the device registry, if the model has one.
    serial_number: str | None

    #: Firmware version reported to the device registry, if the model has one.
    sw_version: str | None

    #: Entity keys the model creates, whether enabled by default or not.
    entity_keys: frozenset[str]

    #: Entity keys the model creates disabled.
    disabled_keys: frozenset[str]

    #: A register the model does not answer for, used to prove that a poll
    #: reads only the blocks it should.
    unused_register: int

    #: Where this model keeps its temperature reading, for tests that need to
    #: write the invalid-reading sentinel into it.
    temperature_register: int

    #: How to make the device stop looking like this model, for probe tests.
    #: Maps a register to a value no genuine device would report there.
    impostor_registers: dict[int, int] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """The model name, as the config entry and device registry hold it."""
        return str(self.model.MODEL)

    @property
    def slug(self) -> str:
        """The model as the config flow's selector offers it.

        Selector options have to be lowercase, so the form and the stored
        entry use different spellings of the same thing.
        """
        return self.name.lower()

    @property
    def user_input(self) -> dict[str, Any]:
        """The address form's contents for this model."""
        return {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_UNIT_ID: self.unit_id,
        }

    @property
    def entry_data(self) -> dict[str, Any]:
        """The config entry data a completed flow should store."""
        return {CONF_MODEL: self.name, **self.user_input}


WS90_CASE = ModelCase(
    model=WS90,
    unit_id=WS90_UNIT_ID,
    registers=WS90_LIVE_EXAMPLE,
    # The device ID WS90_LIVE_EXAMPLE decodes to; see the device library's
    # own ws90/test_ws90.test_serial_number_is_the_device_id.
    unique_id="12345678",
    serial_number="12345678",
    sw_version=None,
    entity_keys=frozenset(
        {
            "light",
            "uv_index",
            "temperature",
            "humidity",
            "wind_speed",
            "gust_speed",
            "wind_direction",
            "rainfall",
            "absolute_pressure",
            "rain_counter",
        }
    ),
    disabled_keys=frozenset({"rain_counter"}),
    # The WS90 archives history up here, but never during a live poll.
    unused_register=0x9B14,
    temperature_register=0x167,
    # Register 0x160 is a fixed device code on a genuine WS90.
    impostor_registers={0x160: 0x42},
)

WN69LP_CASE = ModelCase(
    model=WN69LP,
    unit_id=WN69LP_UNIT_ID,
    registers=WN69LP_LIVE_EXAMPLE,
    # No serial number to key on, so the entry falls back to its address.
    unique_id=f"wn69lp_{MOCK_HOST}_{MOCK_PORT}_{WN69LP_UNIT_ID}",
    serial_number=None,
    sw_version="1.0.0",
    entity_keys=frozenset(
        {
            "light",
            "uv_index",
            "temperature",
            "humidity",
            "wind_speed",
            "gust_speed",
            "wind_direction",
            "rainfall",
            "absolute_pressure",
            "battery_voltage",
            "supply_voltage",
            "recent_rainfall",
        }
    ),
    disabled_keys=frozenset({"supply_voltage", "recent_rainfall"}),
    # Sits in the reserved gap between the config and live blocks, which a
    # correct implementation never reads.
    unused_register=0x170,
    temperature_register=0x182,
    # 101% relative humidity is not something a weather sensor can report.
    impostor_registers={0x183: 101},
)

ALL_MODELS = (WS90_CASE, WN69LP_CASE)
