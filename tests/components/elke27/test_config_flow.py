"""Test the Elke27 config flow."""

from __future__ import annotations

import builtins
import importlib

from homeassistant import config_entries
from homeassistant.components.elke27.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def test_imports_without_elkm1_lib(monkeypatch) -> None:
    """Test that Elke27 imports do not require elkm1_lib."""
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith("elkm1_lib"):
            raise AssertionError("elkm1_lib import attempted")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    importlib.import_module("homeassistant.components.elke27")
    importlib.import_module("homeassistant.components.elke27.config_flow")


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """Test the user step creates an entry without validation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.10",
            CONF_PORT: DEFAULT_PORT,
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "192.168.1.10"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.10",
        CONF_PORT: DEFAULT_PORT,
    }
