"""UniFi Protect siren platform (Public API)."""

import logging
from typing import Any, cast, override

from uiprotect.data import PublicDeviceModel, Siren, SirenDuration

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_VOLUME_LEVEL,
    SirenEntity,
    SirenEntityDescription,
    SirenEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import ProtectDeviceEntity
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


_SIREN_DESCRIPTION = SirenEntityDescription(key="siren")


class ProtectSiren(ProtectDeviceEntity, SirenEntity):
    """Siren entity for a UniFi Protect siren device (Public API)."""

    _attr_name = None  # device name is the entity name
    _attr_supported_features = (
        SirenEntityFeature.TURN_ON
        | SirenEntityFeature.TURN_OFF
        | SirenEntityFeature.DURATION
        | SirenEntityFeature.VOLUME_SET
    )
    _state_attrs = ("_attr_available", "_attr_is_on")
    _ufp_uses_public = True

    def __init__(self, data: ProtectData, siren: Siren) -> None:
        """Initialise the siren entity."""
        # The description key keeps the legacy ``{mac}_siren`` unique ID.
        super().__init__(data, siren, _SIREN_DESCRIPTION)

    @property
    def _siren(self) -> Siren | None:
        return cast(Siren | None, self.data.async_get_public_device(self.device))

    @callback
    @override
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        # A siren gone from the bootstrap (delete event) reads as off.
        siren = cast(Siren | None, self._ufp_public_obj)
        self._attr_is_on = siren is not None and siren.is_active

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
