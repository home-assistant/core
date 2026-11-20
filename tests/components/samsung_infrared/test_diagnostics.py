"""Tests for the Samsung Infrared diagnostics."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import (
    EMITTER_ENTITY_ID as MOCK_INFRARED_ENTITY_ID,
)

from homeassistant.components.samsung_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
    SamsungDeviceType,
)
from homeassistant.components.samsung_infrared.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_diagnostics(hass: HomeAssistant) -> None:
    """Test async_get_config_entry_diagnostics."""

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_TYPE: SamsungDeviceType.TV,
            CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
        },
        unique_id=f"samsung_infrared_tv_infrared.{MOCK_INFRARED_ENTITY_ID}",
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert diagnostics == {
        "infrared_emitter_entity_id": MOCK_INFRARED_ENTITY_ID,
        "device_type": SamsungDeviceType.TV,
        "infrared_emitter_state": "unknown",
    }
