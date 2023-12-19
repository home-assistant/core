"""Test the MPRIS media playback remote control config flow."""
import pytest

from homeassistant.components.mpris.cert_data import CertStore
from homeassistant.core import HomeAssistant


async def test_no_cert_data_raises_keyerror(hass: HomeAssistant) -> None:
    """Test loading absent certificate data raises KeyError."""

    c = CertStore(hass, "nonexistent")
    with pytest.raises(KeyError):
        await c.load_cert_data()


async def test_removals_raise_no_exception(hass: HomeAssistant) -> None:
    """Test removing certificate data raises no exception."""

    c = CertStore(hass, "nonexistent")
    await c.async_remove()
