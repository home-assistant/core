"""Common tests for the Cielo Home climate."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from homeassistant.components.climate import HVACMode
from homeassistant.const import CONF_API_KEY, CONF_TOKEN, UnitOfTemperature
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DOMAIN = "cielo_home"


async def test_climate_set_temperature_calls_library(
    hass: HomeAssistant, mock_cielo_client: MagicMock
) -> None:
    """Test setting temperature calls into the library client/device API."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key", CONF_TOKEN: "valid-test-token"},
    )
    entry.add_to_hass(hass)

    device_api = MagicMock()
    device_api.temperature_unit.return_value = "°C"
    device_api.min_temp.return_value = 10
    device_api.max_temp.return_value = 35
    device_api.target_temperature_step.return_value = 1
    device_api.hvac_mode.return_value = HVACMode.COOL
    device_api.hvac_modes.return_value = [HVACMode.OFF, HVACMode.COOL]
    device_api.mode_supports_temperature.return_value = True
    device_api.mode_caps.return_value = {"fan_levels": True, "swing": True}
    device_api.current_temperature.return_value = 22
    device_api.target_temperature.return_value = 24
    device_api.fan_modes.return_value = ["auto", "low", "high"]
    device_api.preset_modes.return_value = ["home", "away"]
    device_api.swing_modes.return_value = ["auto", "pos1", "pos2"]
    device_api.async_set_temperature = AsyncMock(
        return_value={"data": {"target_temperature": 25}}
    )

    with patch(
        "homeassistant.components.cielo_home.entity.CieloBaseEntity.client",
        new_callable=PropertyMock,
        return_value=device_api,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = next(
            s
            for s in hass.states.async_all("climate")
            if s.entity_id.startswith("climate.")
            and s.attributes.get("device_class") is None
        )

        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": state.entity_id, "temperature": 25},
            blocking=True,
        )

        device_api.async_set_temperature.assert_awaited_once_with(
            UnitOfTemperature.CELSIUS,
            entity_id=[state.entity_id],
            temperature=25.0,
        )
