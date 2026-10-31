"""Support for iCloud buttons."""

from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .account import IcloudAccount, IcloudConfigEntry, IcloudDevice
from .entity import IcloudDeviceEntity

# Playing a sound is a blocking request to Apple, so serialize the presses.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IcloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons for iCloud devices."""
    account = entry.runtime_data
    tracked = set[str]()

    @callback
    def update_account() -> None:
        """Add buttons for devices that appeared since the last poll."""
        add_entities(account, async_add_entities, tracked)

    account.listeners.append(
        async_dispatcher_connect(hass, account.signal_device_new, update_account)
    )

    update_account()


@callback
def add_entities(
    account: IcloudAccount,
    async_add_entities: AddConfigEntryEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add buttons for devices that can play a sound."""
    new_entities = []

    for dev_id, device in account.devices.items():
        if dev_id in tracked or not device.sound_available:
            continue

        new_entities.append(IcloudPlaySoundButton(account, device))
        tracked.add(dev_id)

    async_add_entities(new_entities)


class IcloudPlaySoundButton(IcloudDeviceEntity, ButtonEntity):
    """Representation of an iCloud play sound button."""

    _attr_translation_key = "play_sound"

    def __init__(self, account: IcloudAccount, device: IcloudDevice) -> None:
        """Initialize the play sound button."""
        super().__init__(account, device)
        self._attr_unique_id = f"{device.unique_id}_play_sound"

    @override
    async def async_press(self) -> None:
        """Play the lost device sound on the device."""
        await self.hass.async_add_executor_job(self._device.play_sound)
