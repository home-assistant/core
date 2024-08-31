"""Test the Tessie number platform."""


from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.components.tessie.number import DESCRIPTIONS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .common import TEST_VEHICLE_STATE_ONLINE, patch_description, setup_platform


async def test_numbers(hass: HomeAssistant) -> None:
    """Tests that the number entities are correct."""

    assert len(hass.states.async_all("number")) == 0

    await setup_platform(hass)

    assert len(hass.states.async_all("number")) == len(DESCRIPTIONS)

    assert hass.states.get("number.test_charge_current").state == str(
        TEST_VEHICLE_STATE_ONLINE["charge_state"]["charge_current_request"]
    )

    assert hass.states.get("number.test_charge_limit").state == str(
        TEST_VEHICLE_STATE_ONLINE["charge_state"]["charge_limit_soc"]
    )

    assert hass.states.get("number.test_speed_limit").state == str(
        TEST_VEHICLE_STATE_ONLINE["vehicle_state"]["speed_limit_mode"][
            "current_limit_mph"
        ]
    )

    # Test number set value functions
    with patch_description(
        "charge_state_charge_current_request", "func", DESCRIPTIONS
    ) as mock_set_charging_amps:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ["number.test_charge_current"], "value": 16},
            blocking=True,
        )
        assert hass.states.get("number.test_charge_current").state == "16.0"
        mock_set_charging_amps.assert_called_once()

    with patch_description(
        "charge_state_charge_limit_soc", "func", DESCRIPTIONS
    ) as mock_set_charge_limit:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ["number.test_charge_limit"], "value": 80},
            blocking=True,
        )
        assert hass.states.get("number.test_charge_limit").state == "80.0"
        mock_set_charge_limit.assert_called_once()

    with patch_description(
        "vehicle_state_speed_limit_mode_current_limit_mph", "func", DESCRIPTIONS
    ) as mock_set_speed_limit:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ["number.test_speed_limit"], "value": 60},
            blocking=True,
        )
        assert hass.states.get("number.test_speed_limit").state == "60.0"
        mock_set_speed_limit.assert_called_once()
