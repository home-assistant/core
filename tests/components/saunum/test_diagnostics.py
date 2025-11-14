"""Test Saunum Leil Sauna diagnostics."""

import re

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics.

    The diagnostics include a dynamic human readable uptime field
    (on_time_formatted) which we validate separately for pattern
    correctness before snapshotting the remaining structure.
    """
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )

    # Validate presence and format of formatted uptime if available
    if "on_time_formatted" in diagnostics:
        value = diagnostics["on_time_formatted"]
        assert isinstance(value, str)
        assert re.fullmatch(r"^\d+d \d+h \d+m \d+s$", value)

    # Snapshot remaining stable data (exclude dynamic field)
    stable = dict(diagnostics)
    stable.pop("on_time_formatted", None)
    assert stable == snapshot
