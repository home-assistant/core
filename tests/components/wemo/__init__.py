"""The tests for WeMo component."""

from homeassistant.components.wemo import WEMO_MODEL_DISPATCH
from homeassistant.components.wemo.const import DOMAIN

from tests.async_mock import patch
from tests.common import MockConfigEntry


class DeviceTests:
    """Basic name/id/info tests for all wemo device entities."""

    DEVICE_MODEL = "WeMoDevice"
    DEVICE_SERIAL_NUMBER = "wemodevice_serialnumber"
    DEVICE_NAME = "wemodevice_name"

    def test_name(self, wemo_device):
        """Verify the device name."""
        assert wemo_device.name == self.DEVICE_NAME

    def test_unique_id(self, wemo_device):
        """Verify the unique id."""
        assert wemo_device.unique_id == self.DEVICE_SERIAL_NUMBER

    def test_device_info(self, wemo_device):
        """Verify the device info."""
        assert wemo_device.device_info == {
            "name": self.DEVICE_NAME,
            "identifiers": {(DOMAIN, self.DEVICE_SERIAL_NUMBER)},
            "model": self.DEVICE_MODEL,
            "manufacturer": "Belkin",
        }


class SubscriptionTests:
    """Test that push subscriptions are working."""

    async def test_update_basic_state(self, hass, wemo_device, pywemo_registry):
        """A subscription callback will update the device _state."""
        hass.data.setdefault(DOMAIN, {}).setdefault("registry", pywemo_registry)
        wemo_device.hass = hass
        wemo_device.async_write_ha_state = lambda: None

        # This should register the wemo for push updates.
        await wemo_device.async_added_to_hass()
        assert pywemo_registry.on.called

        wemo_device.wemo.subscription_update.return_value = True
        wemo_device.wemo.get_state.return_value = "final_state"
        callback = pywemo_registry.on.call_args[0][2]

        # Test that the push update is successful.
        callback(wemo_device.wemo, "BinaryState", "1")
        await hass.async_block_till_done()
        assert wemo_device.wemo.subscription_update.called
        assert wemo_device.wemo.get_state.called
        assert wemo_device._state == "final_state"


class ConfigEntryTests:
    """Test that the entry is setup properly."""

    async def add_entity(self, hass, pywemo_device, pywemo_registry):
        """Add entity to home assistant."""
        entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
        with patch("pywemo.discover_devices", return_value=[pywemo_device]), patch(
            "pywemo.SubscriptionRegistry", return_value=pywemo_registry
        ):
            entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

    async def test_async_setup_entry(self, hass, pywemo_device, pywemo_registry):
        """Test that the entity is created successfully."""
        await self.add_entity(hass, pywemo_device, pywemo_registry)
        component = WEMO_MODEL_DISPATCH[self.DEVICE_MODEL]
        state = hass.states.get(f"{component}.{pywemo_device.name}")
        assert state is not None
