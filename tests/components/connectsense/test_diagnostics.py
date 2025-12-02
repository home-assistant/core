import pytest

pytest.importorskip("tests.components.diagnostics")

from tests.components.diagnostics import get_diagnostics_for_config_entry

DOMAIN = "connectsense"

async def test_diagnostics(hass, hass_client, setup_entry):
    data = await get_diagnostics_for_config_entry(hass, hass_client, setup_entry)
    assert isinstance(data, dict)
    assert "config_entry" in data
    assert "device_registry" in data or "devices" in data or "entities" in data
    # crude redaction check: sensitive keys are present but redacted/None
    cfg = data["config_entry"]["data"]
    assert cfg.get("webhook_token_current") in (None, "**REDACTED**")
    assert cfg.get("webhook_token_prev") in (None, "**REDACTED**")
    assert cfg.get("webhook_id") in (None, "**REDACTED**")


async def test_runtime_data_set(hass, hass_client, setup_entry):
    entry = setup_entry
    assert entry.runtime_data is not None
    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.runtime_data.store is hass.data[DOMAIN][entry.entry_id]


async def test_runtime_data_in_diagnostics(hass, hass_client, setup_entry):
    entry = setup_entry
    diag = await get_diagnostics_for_config_entry(hass, hass_client, setup_entry)
    # runtime store exists and differs from live (redacted)
    assert "store" in diag["integration_runtime"]
    assert diag["integration_runtime"]["store"] != entry.runtime_data.store
