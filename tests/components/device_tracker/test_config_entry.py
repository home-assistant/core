"""Test Device Tracker config entry things."""
from homeassistant.components.device_tracker import DOMAIN, config_entry as ce
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from tests.common import (
    MockConfigEntry,
    MockEntityPlatform,
    MockPlatform,
    mock_registry,
)


def test_tracker_entity():
    """Test tracker entity."""

    class TestEntry(ce.TrackerEntity):
        """Mock tracker class."""

        should_poll = False

    instance = TestEntry()

    assert instance.force_update

    instance.should_poll = True

    assert not instance.force_update


async def test_cleanup_legacy(hass, enable_custom_integrations):
    """Test we clean up devices created by old device tracker."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    device1 = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "device1")}
    )
    device2 = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "device2")}
    )
    device3 = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "device3")}
    )

    # Device with light + device tracker entity
    entity1a = ent_reg.async_get_or_create(
        DOMAIN,
        "test",
        "entity1a-unique",
        config_entry=config_entry,
        device_id=device1.id,
    )
    entity1b = ent_reg.async_get_or_create(
        "light",
        "test",
        "entity1b-unique",
        config_entry=config_entry,
        device_id=device1.id,
    )
    # Just device tracker entity
    entity2a = ent_reg.async_get_or_create(
        DOMAIN,
        "test",
        "entity2a-unique",
        config_entry=config_entry,
        device_id=device2.id,
    )
    # Device with no device tracker entities
    entity3a = ent_reg.async_get_or_create(
        "light",
        "test",
        "entity3a-unique",
        config_entry=config_entry,
        device_id=device3.id,
    )
    # Device tracker but no device
    entity4a = ent_reg.async_get_or_create(
        DOMAIN,
        "test",
        "entity4a-unique",
        config_entry=config_entry,
    )
    # Completely different entity
    entity5a = ent_reg.async_get_or_create(
        "light",
        "test",
        "entity4a-unique",
        config_entry=config_entry,
    )

    await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
    await hass.async_block_till_done()

    for entity in (entity1a, entity1b, entity3a, entity4a, entity5a):
        assert ent_reg.async_get(entity.entity_id) is not None

    # We've removed device so device ID cleared
    assert ent_reg.async_get(entity2a.entity_id).device_id is None
    # Removed because only had device tracker entity
    assert dev_reg.async_get(device2.id) is None


async def test_register_mac(hass):
    """Test registering a mac."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    mac1 = "12:34:56:AB:CD:EF"

    entity_entry_1 = ent_reg.async_get_or_create(
        "device_tracker",
        "test",
        mac1 + "yo1",
        original_name="name 1",
        config_entry=config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    ce._async_register_mac(hass, "test", mac1, mac1 + "yo1")

    dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac1)},
    )

    await hass.async_block_till_done()

    entity_entry_1 = ent_reg.async_get(entity_entry_1.entity_id)

    assert entity_entry_1.disabled_by is None


async def test_register_mac_ignored(hass):
    """Test ignoring registering a mac."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    config_entry = MockConfigEntry(domain="test", pref_disable_new_entities=True)
    config_entry.add_to_hass(hass)

    mac1 = "12:34:56:AB:CD:EF"

    entity_entry_1 = ent_reg.async_get_or_create(
        "device_tracker",
        "test",
        mac1 + "yo1",
        original_name="name 1",
        config_entry=config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    ce._async_register_mac(hass, "test", mac1, mac1 + "yo1")

    dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac1)},
    )

    await hass.async_block_till_done()

    entity_entry_1 = ent_reg.async_get(entity_entry_1.entity_id)

    assert entity_entry_1.disabled_by == er.RegistryEntryDisabler.INTEGRATION


async def test_connected_device_registered(hass):
    """Test dispatch on connected device being registered."""

    registry = mock_registry(hass)
    dispatches = []

    @callback
    def _save_dispatch(msg):
        dispatches.append(msg)

    unsub = async_dispatcher_connect(
        hass, ce.CONNECTED_DEVICE_REGISTERED, _save_dispatch
    )

    class MockScannerEntity(ce.ScannerEntity):
        """Mock a scanner entity."""

        @property
        def ip_address(self) -> str:
            return "5.4.3.2"

        @property
        def unique_id(self) -> str:
            return self.mac_address

    class MockDisconnectedScannerEntity(MockScannerEntity):
        """Mock a disconnected scanner entity."""

        @property
        def mac_address(self) -> str:
            return "aa:bb:cc:dd:ee:ff"

        @property
        def is_connected(self) -> bool:
            return True

        @property
        def hostname(self) -> str:
            return "connected"

    class MockConnectedScannerEntity(MockScannerEntity):
        """Mock a disconnected scanner entity."""

        @property
        def mac_address(self) -> str:
            return "aa:bb:cc:dd:ee:00"

        @property
        def is_connected(self) -> bool:
            return False

        @property
        def hostname(self) -> str:
            return "disconnected"

    async def async_setup_entry(hass, config_entry, async_add_entities):
        """Mock setup entry method."""
        async_add_entities(
            [MockConnectedScannerEntity(), MockDisconnectedScannerEntity()]
        )
        return True

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry(entry_id="super-mock-id")
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    assert await entity_platform.async_setup_entry(config_entry)
    await hass.async_block_till_done()
    full_name = f"{entity_platform.domain}.{config_entry.domain}"
    assert full_name in hass.config.components
    assert len(hass.states.async_entity_ids()) == 0  # should be disabled
    assert len(registry.entities) == 2
    assert (
        registry.entities["test_domain.test_aa_bb_cc_dd_ee_ff"].config_entry_id
        == "super-mock-id"
    )
    unsub()
    assert dispatches == [
        {"ip": "5.4.3.2", "mac": "aa:bb:cc:dd:ee:ff", "host_name": "connected"}
    ]
