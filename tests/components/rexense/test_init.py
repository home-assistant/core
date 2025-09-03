import inspect

from homeassistant.components.rexense import async_setup_entry, async_unload_entry

def test_async_setup_entry_signature():
    sig = inspect.signature(async_setup_entry)
    assert list(sig.parameters) == ["hass", "entry"]

def test_async_unload_entry_signature():
    sig = inspect.signature(async_unload_entry)
    assert list(sig.parameters) == ["hass", "entry"]