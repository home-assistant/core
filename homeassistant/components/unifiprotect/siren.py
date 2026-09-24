"""UniFi Protect siren platform (Public API)."""

import logging
from typing import Any, override

from uiprotect.data import DeviceState, PublicDeviceModel, Siren, SirenDuration

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_VOLUME_LEVEL,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEFAULT_ATTRIBUTION, DEFAULT_BRAND, DOMAIN
from .data import ProtectData, UFPConfigEntry
from .utils import async_ufp_instance_command

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# Durations (in seconds) accepted by the UniFi Protect siren public API.
VALID_DURATIONS: tuple[int, ...] = tuple(d.value for d in SirenDuration)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up UniFi Protect siren entities from a config entry."""
    data: ProtectData = entry.runtime_data

    @callback
    def _add_new_public_device(device: PublicDeviceModel) -> None:
        # A siren has no private counterpart, so the adopt path never offers
        # one; it arrives through the public add signal in both modes.
        if isinstance(device, Siren):
            async_add_entities([ProtectSiren(data, device)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, data.public_add_signal, _add_new_public_device)
    )

    api = data.api
    if not api.has_public_bootstrap:
        return

    async_add_entities(
        ProtectSiren(data, siren) for siren in api.public_bootstrap.sirens.values()
    )


class ProtectSiren(SirenEntity):
    """Siren entity for a UniFi Protect siren device (Public API)."""

    _attr_has_entity_name = True
    _attr_attribution = DEFAULT_ATTRIBUTION
    _attr_name = None  # device name is the entity name
    _attr_should_poll = False
    _attr_supported_features = (
        SirenEntityFeature.TURN_ON
        | SirenEntityFeature.TURN_OFF
        | SirenEntityFeature.DURATION
        | SirenEntityFeature.VOLUME_SET
    )

    def __init__(self, data: ProtectData, siren: Siren) -> None:
        """Initialise the siren entity."""
        self.data = data
        self._siren_id = siren.id
        self._attr_unique_id = f"{siren.mac}_siren"  # pylint: disable=home-assistant-entity-unique-id-redundant-platform
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, siren.mac)},
            identifiers={(DOMAIN, siren.mac)},
            manufacturer=DEFAULT_BRAND,
            name=siren.name,
            model="Siren",
            via_device_id=data.nvr_device_id,
        )
        self._siren_mac = siren.mac
        self._update_from_siren(siren)

    @property
    def _siren(self) -> Siren | None:
        api = self.data.api
        if not api.has_public_bootstrap:
            return None
        return api.public_bootstrap.sirens.get(self._siren_id)

    @callback
    def _update_from_siren(self, siren: Siren) -> None:
        """Refresh cached attributes from the siren object."""
        # A siren that dropped off the console stays in the bootstrap.
        self._attr_available = (
            self.data.last_public_update_success
            and siren.state is DeviceState.CONNECTED
        )
        self._attr_is_on = siren.is_active

    @callback
    def _async_updated(self, _obj: PublicDeviceModel | None) -> None:
        """Handle a public devices WS update for this siren.

        The state is always re-read from the public bootstrap: the library
        merges WS updates into it before dispatching, and ``None`` carries no
        object to read. A timed run ending is announced by the library as a
        regular update.
        """
        prev_state = (self._attr_available, self._attr_is_on)

        if (siren := self._siren) is None:
            # Gone from the bootstrap (delete event): mark unavailable and off.
            self._attr_available = False
            self._attr_is_on = False
        else:
            self._update_from_siren(siren)

        if (self._attr_available, self._attr_is_on) != prev_state:
            self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to public WS updates dispatched by ProtectData."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.data.async_subscribe_public(self._siren_mac, self._async_updated)
        )
        # Refresh from the bootstrap: a WS update or delete that landed between
        # entity construction and this subscription would otherwise be missed.
        self._async_updated(None)

    @async_ufp_instance_command
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate the siren, optionally for a given duration and/or volume."""
        if (siren := self._siren) is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="siren_not_available",
            )

        duration: int | None = kwargs.get(ATTR_DURATION)
        volume_level: float | None = kwargs.get(ATTR_VOLUME_LEVEL)

        # Validate duration first (synchronous) before making any API calls.
        norm_duration: SirenDuration | None = None
        if duration is not None:
            try:
                norm_duration = SirenDuration(duration)
            except ValueError:
                valid = ", ".join(str(v) for v in VALID_DURATIONS)
                _LOGGER.debug(
                    "Rejected invalid siren duration %ds for %s (valid: %s s)",
                    duration,
                    siren.name,
                    valid,
                )
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="siren_invalid_duration",
                    translation_placeholders={
                        "duration": str(duration),
                        "valid": valid,
                    },
                ) from None

        # Set volume if requested (separate API call).
        if volume_level is not None:
            # HA passes volume as 0.0-1.0; UFP expects 0-100.
            await siren.set_volume(round(volume_level * 100))

        await siren.play(duration=norm_duration)

    @async_ufp_instance_command
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the siren."""
        if (siren := self._siren) is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="siren_not_available",
            )
        await siren.stop()
        # The server does not emit a WS event after a manual stop, so we set
        # the state optimistically.
        self._attr_is_on = False
        self.async_write_ha_state()
