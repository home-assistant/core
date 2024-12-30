"""Test the Tado coordinator."""

from unittest.mock import patch

import PyTado
import PyTado.exceptions
import pytest

from homeassistant.components.tado.const import DOMAIN
from homeassistant.components.tado.coordinator import TadoDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import UpdateFailed

from .util import async_init_integration

from tests.common import MockConfigEntry, SnapshotAssertion


@pytest.mark.parametrize(
    ("exception", "expected_exception", "expected_message"),
    [
        (
            PyTado.exceptions.TadoWrongCredentialsException("Invalid credentials"),
            ConfigEntryError,
            "Invalid Tado credentials. Error: Invalid credentials",
        ),
        (
            PyTado.exceptions.TadoException("General error"),
            UpdateFailed,
            "Error during Tado setup: General error",
        ),
    ],
)
async def test_coordinator_setup_exceptions(
    hass: HomeAssistant, exception, expected_exception, expected_message
) -> None:
    """Test the Tado coordinator setup exceptions."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "mock", "password": "mock"},
        options={"fallback": "NEXT_TIME_BLOCK"},
    )
    config_entry.add_to_hass(hass)

    coordinator = TadoDataUpdateCoordinator(
        hass=hass, username="mock", password="mock", fallback="NEXT_TIME_BLOCK"
    )

    with patch(
        "PyTado.interface.Tado.__init__",
        side_effect=exception,
    ) as mock_tado_init:
        mock_tado_init.return_value = None
        with pytest.raises(expected_exception) as exc:
            await coordinator._async_setup()

    assert expected_message in str(exc.value)


async def test_coordinator_successful_setup(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test the Tado coordinator setup."""

    await async_init_integration(hass)
    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]

    assert config_entry.runtime_data == snapshot
