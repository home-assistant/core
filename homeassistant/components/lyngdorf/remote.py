"""Remote platform for Lyngdorf integration."""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, override

from lyngdorf import LyngdorfReceiver, LyngdorfUnsupportedError, Remote

from homeassistant.components.remote import ATTR_NUM_REPEATS, RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import LyngdorfEntity
from .models import LyngdorfConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LyngdorfConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lyngdorf remote from a config entry."""
    runtime_data = config_entry.runtime_data
    receiver = runtime_data.receiver

    # The TDAI family has no remote keys at all, so it gets no remote entity.
    if receiver.remote is None:
        return

    async_add_entities(
        [LyngdorfRemote(receiver, config_entry, runtime_data.device_info)]
    )


class LyngdorfRemote(LyngdorfEntity, RemoteEntity):
    """Lyngdorf remote entity."""

    _attr_name = None

    def __init__(
        self,
        receiver: LyngdorfReceiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the remote."""
        super().__init__(receiver, device_info)
        if TYPE_CHECKING:
            assert config_entry.unique_id
        self._attr_unique_id = config_entry.unique_id

    @property
    def _remote(self) -> Remote:
        """Return the remote; this entity exists only when the model has one."""
        remote = self._receiver.remote
        if TYPE_CHECKING:
            assert remote is not None
        return remote

    @override
    @property
    def is_on(self) -> bool | None:
        """Return whether the device is on."""
        return self._receiver.power_on

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._receiver.set_power(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._receiver.set_power(False)

    @override
    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a sequence of remote keys to the device."""
        # delay_secs is dropped: the library already paces its own writes.
        try:
            await self._remote.send(command, num_repeats=kwargs[ATTR_NUM_REPEATS])
        except LyngdorfUnsupportedError as err:
            # The member value is what a caller sends: DIGIT_0 is "0", not "digit_0".
            keys = sorted(key.value for key in self._remote.keys)
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_remote_key",
                translation_placeholders={"keys": ", ".join(keys)},
            ) from err
