"""Support for interfacing with Monoprice 6 zone home audio controller."""
import logging

from serial import SerialException

from homeassistant import core
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform, service
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_SOURCES,
    DOMAIN,
    FIRST_RUN,
    MONOPRICE_OBJECT,
    SERVICE_RESTORE,
    SERVICE_SNAPSHOT,
)

_LOGGER = logging.getLogger(__name__)

MAX_VOLUME = 38
PARALLEL_UPDATES = 1


@core.callback
def _get_sources_from_dict(data):
    sources_config = data[CONF_SOURCES]

    source_id_name = {int(index): name for index, name in sources_config.items()}

    source_name_id = {v: k for k, v in source_id_name.items()}

    source_names = sorted(source_name_id.keys(), key=lambda v: source_name_id[v])

    return [source_id_name, source_name_id, source_names]


@core.callback
def _get_sources(config_entry):
    if CONF_SOURCES in config_entry.options:
        data = config_entry.options
    else:
        data = config_entry.data
    return _get_sources_from_dict(data)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Monoprice 6-zone amplifier platform."""
    port = config_entry.data[CONF_PORT]

    monoprice = hass.data[DOMAIN][config_entry.entry_id][MONOPRICE_OBJECT]

    sources = _get_sources(config_entry)

    entities = []
    for i in range(1, 4):
        for j in range(1, 7):
            zone_id = (i * 10) + j
            _LOGGER.info("Adding zone %d for port %s", zone_id, port)
            entities.append(
                MonopriceZone(monoprice, sources, config_entry.entry_id, zone_id)
            )

    # only call update before add if it's the first run so we can try to detect zones
    first_run = hass.data[DOMAIN][config_entry.entry_id][FIRST_RUN]
    async_add_entities(entities, first_run)

    platform = entity_platform.async_get_current_platform()

    def _call_service(entities, service_call):
        for entity in entities:
            if service_call.service == SERVICE_SNAPSHOT:
                entity.snapshot()
            elif service_call.service == SERVICE_RESTORE:
                entity.restore()

    @service.verify_domain_control(hass, DOMAIN)
    async def async_service_handle(service_call: core.ServiceCall) -> None:
        """Handle for services."""
        entities = await platform.async_extract_from_service(service_call)

        if not entities:
            return

        hass.async_add_executor_job(_call_service, entities, service_call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SNAPSHOT,
        async_service_handle,
        schema=cv.make_entity_service_schema({}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESTORE,
        async_service_handle,
        schema=cv.make_entity_service_schema({}),
    )


class MonopriceZone(MediaPlayerEntity):
    """Representation of a Monoprice amplifier zone."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, monoprice, sources, namespace, zone_id):
        """Initialize new zone."""
        self._monoprice = monoprice
        # dict source_id -> source name
        self._source_id_name = sources[0]
        # dict source name -> source_id
        self._source_name_id = sources[1]
        # ordered list of all source names
        self._attr_source_list = sources[2]
        self._zone_id = zone_id
        self._attr_unique_id = f"{namespace}_{self._zone_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Monoprice",
            model="6-Zone Amplifier",
            name=f"Zone {self._zone_id}",
        )

        self._snapshot = None
        self._update_success = True

    def update(self) -> None:
        """Retrieve latest state."""
        try:
            state = self._monoprice.zone_status(self._zone_id)
        except SerialException:
            self._update_success = False
            _LOGGER.warning("Could not update zone %d", self._zone_id)
            return

        if not state:
            self._update_success = False
            return

        self._attr_state = MediaPlayerState.ON if state.power else MediaPlayerState.OFF
        self._attr_volume_level = state.volume / MAX_VOLUME
        self._attr_is_volume_muted = state.mute
        idx = state.source
        self._attr_source = self._source_id_name.get(idx)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._zone_id < 20 or self._update_success

    @property
    def media_title(self):
        """Return the current source as medial title."""
        return self.source

    def snapshot(self):
        """Save zone's current state."""
        self._snapshot = self._monoprice.zone_status(self._zone_id)

    def restore(self):
        """Restore saved state."""
        if self._snapshot:
            self._monoprice.restore_zone(self._snapshot)
            self.schedule_update_ha_state(True)

    def select_source(self, source: str) -> None:
        """Set input source."""
        if source not in self._source_name_id:
            return
        idx = self._source_name_id[source]
        self._monoprice.set_source(self._zone_id, idx)

    def turn_on(self) -> None:
        """Turn the media player on."""
        self._monoprice.set_power(self._zone_id, True)

    def turn_off(self) -> None:
        """Turn the media player off."""
        self._monoprice.set_power(self._zone_id, False)

    def mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        self._monoprice.set_mute(self._zone_id, mute)

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._monoprice.set_volume(self._zone_id, round(volume * MAX_VOLUME))

    def volume_up(self) -> None:
        """Volume up the media player."""
        if self.volume_level is None:
            return
        volume = round(self.volume_level * MAX_VOLUME)
        self._monoprice.set_volume(self._zone_id, min(volume + 1, MAX_VOLUME))

    def volume_down(self) -> None:
        """Volume down media player."""
        if self.volume_level is None:
            return
        volume = round(self.volume_level * MAX_VOLUME)
        self._monoprice.set_volume(self._zone_id, max(volume - 1, 0))
