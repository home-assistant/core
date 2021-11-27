"""Light platform tests for the decora_wifi module."""

from unittest.mock import patch

from homeassistant.components.decora_wifi.const import DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS,
    SUPPORT_TRANSITION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry
from tests.components.decora_wifi.common import (
    MANUFACTURER,
    VERSION,
    FakeDecoraWiFiAccount,
    FakeDecoraWiFiIotSwitch,
    FakeDecoraWiFiResidence,
    FakeDecoraWiFiResidentialAccount,
    FakeDecoraWiFiSession,
)

TEST_USERNAME = "username@home-assisant.io"
TEST_PASSWORD = "test-password"


async def setup_platform(hass):
    """Load the platform in preparation for a test."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USERNAME,
        data={
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_light_platform_setup(hass: HomeAssistant):
    """Test light platform setup."""
    # Load Registries
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    # Arrange Fake API State
    FakeDecoraWiFiIotSwitch.reset_counter()
    FakeDecoraWiFiSession.clear_accounts()
    FakeDecoraWiFiSession.add_account(
        FakeDecoraWiFiAccount(
            TEST_USERNAME, TEST_PASSWORD, switch_models=["D26HD", "DW15P"]
        )
    )
    # Conduct Tests
    with patch(
        "homeassistant.components.decora_wifi.common.DecoraWiFiSession",
        side_effect=FakeDecoraWiFiSession,
    ), patch(
        "homeassistant.components.decora_wifi.common.Residence",
        side_effect=FakeDecoraWiFiResidence,
    ), patch(
        "homeassistant.components.decora_wifi.common.ResidentialAccount",
        side_effect=FakeDecoraWiFiResidentialAccount,
    ):
        # Set up the integration
        config_entry = await setup_platform(hass)

        # Assert the entity state
        light_1_a = hass.states.get("light.fake_switch_1")
        assert light_1_a is not None
        assert light_1_a.state == "on"
        assert light_1_a.attributes["brightness"] == 255

        light_2 = hass.states.get("light.fake_switch_2")
        assert light_2 is not None
        assert light_2.state == "on"

        # Assert Entity Registry RegistryEntry state
        entity_reg_entry_1 = entity_registry.async_get("light.fake_switch_1")
        assert entity_reg_entry_1 is not None
        assert (
            entity_reg_entry_1.supported_features
            == SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION
        )
        assert entity_reg_entry_1.unique_id == "DE-AD-BE-EF-00-01"
        entity_reg_entry_2 = entity_registry.async_get("light.fake_switch_2")
        assert entity_reg_entry_2 is not None
        assert entity_reg_entry_2.supported_features == 0
        assert entity_reg_entry_2.unique_id == "DE-AD-BE-EF-00-02"

        # Assert Device Registry DeviceEntry state
        device_reg_entry_1 = device_registry.async_get(entity_reg_entry_1.device_id)
        assert device_reg_entry_1 is not None
        assert device_reg_entry_1.model == "D26HD"
        assert device_reg_entry_1.manufacturer == MANUFACTURER
        assert device_reg_entry_1.sw_version == VERSION
        device_reg_entry_2 = device_registry.async_get(entity_reg_entry_2.device_id)
        assert device_reg_entry_2 is not None
        assert device_reg_entry_2.model == "DW15P"

        # Assert ConfigEntry State
        assert config_entry.state is ConfigEntryState.LOADED
        session = hass.data[DOMAIN][config_entry.entry_id]
        assert session is not None


async def test_light_state_changes(hass: HomeAssistant):
    """Test light state changes."""
    # Arrange Fake API State
    FakeDecoraWiFiIotSwitch.reset_counter()
    FakeDecoraWiFiSession.clear_accounts()
    FakeDecoraWiFiSession.add_account(
        FakeDecoraWiFiAccount(TEST_USERNAME, TEST_PASSWORD, switch_models=["D26HD"])
    )
    # Conduct Tests
    with patch(
        "homeassistant.components.decora_wifi.common.DecoraWiFiSession",
        side_effect=FakeDecoraWiFiSession,
    ), patch(
        "homeassistant.components.decora_wifi.common.Residence",
        side_effect=FakeDecoraWiFiResidence,
    ), patch(
        "homeassistant.components.decora_wifi.common.ResidentialAccount",
        side_effect=FakeDecoraWiFiResidentialAccount,
    ):
        # Set up the integration
        await setup_platform(hass)

        # Assert the entity state
        light_1_a = hass.states.get("light.fake_switch_1")
        assert light_1_a is not None
        assert light_1_a.state == "on"
        assert light_1_a.attributes["brightness"] == 255

        # Send a turn off command
        await hass.services.async_call(
            "light", "turn_off", {"entity_id": "light.fake_switch_1"}, blocking=True
        )

        # Verify the state transition
        light_1_b = hass.states.get("light.fake_switch_1")
        assert light_1_b.state == "off"

        # Send a turn on command with brightness and transition speed
        await hass.services.async_call(
            "light",
            "turn_on",
            {
                "entity_id": "light.fake_switch_1",
                ATTR_BRIGHTNESS: 127,
                ATTR_TRANSITION: 5,
            },
            blocking=True,
        )

        # Verify the state transition
        light_1_c = hass.states.get("light.fake_switch_1")
        assert light_1_c is not None
        assert light_1_c.state == "on"
        assert light_1_c.attributes[ATTR_BRIGHTNESS] == int(
            int(127 * 100 / 255) * 255 / 100
        )


async def test_comm_failure(hass: HomeAssistant):
    """Test behavior against simulated API comm failure."""
    # Arrange Fake API State
    FakeDecoraWiFiIotSwitch.reset_counter()
    FakeDecoraWiFiSession.clear_accounts()
    FakeDecoraWiFiSession.add_account(
        FakeDecoraWiFiAccount(TEST_USERNAME, TEST_PASSWORD, switch_models=["D26HD"])
    )
    # Conduct Tests
    with patch(
        "homeassistant.components.decora_wifi.common.DecoraWiFiSession",
        side_effect=FakeDecoraWiFiSession,
    ), patch(
        "homeassistant.components.decora_wifi.common.Residence",
        side_effect=FakeDecoraWiFiResidence,
    ), patch(
        "homeassistant.components.decora_wifi.common.ResidentialAccount",
        side_effect=FakeDecoraWiFiResidentialAccount,
    ):
        # Set up the integration
        config_entry = await setup_platform(hass)
        session = hass.data[DOMAIN][config_entry.entry_id]._session

        session.comms_good = False

        # Send a turn off command
        await hass.services.async_call(
            "light", "turn_off", {"entity_id": "light.fake_switch_1"}, blocking=True
        )

        # Verify the state transition has not occurred
        light_1_b = hass.states.get("light.fake_switch_1")
        assert light_1_b.state == "on"

        # Send a 'turn on' command with a different brightness
        await hass.services.async_call(
            "light",
            "turn_on",
            {
                "entity_id": "light.fake_switch_1",
                ATTR_BRIGHTNESS: 127,
                ATTR_TRANSITION: 5,
            },
            blocking=True,
        )

        # Verify the state transition has not occurred
        light_1_c = hass.states.get("light.fake_switch_1")
        assert light_1_c is not None
        assert light_1_c.attributes[ATTR_BRIGHTNESS] == 255
