"""The Bang & Olufsen integration."""
from __future__ import annotations

import logging

from mozart_api.mozart_client import MozartClient
from urllib3.exceptions import MaxRetryError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from .binary_sensor import (
    BangOlufsenBinarySensor,
    BangOlufsenBinarySensorBatteryCharging,
    BangOlufsenBinarySensorProximity,
)
from .button import BangOlufsenButtonFavourite
from .const import DOMAIN, EntityEnum, ModelEnum, SupportEnum
from .coordinator import BangOlufsenCoordinator
from .media_player import BangOlufsenMediaPlayer
from .number import BangOlufsenNumber, BangOlufsenNumberBass, BangOlufsenNumberTreble
from .select import (
    BangOlufsenSelect,
    BangOlufsenSelectListeningPosition,
    BangOlufsenSelectSoundMode,
)
from .sensor import (
    BangOlufsenSensor,
    BangOlufsenSensorBatteryChargingTime,
    BangOlufsenSensorBatteryLevel,
    BangOlufsenSensorBatteryPlayingTime,
    BangOlufsenSensorInputSignal,
    BangOlufsenSensorMediaId,
)
from .switch import BangOlufsenSwitch, BangOlufsenSwitchLoudness
from .text import (
    BangOlufsenText,
    BangOlufsenTextFriendlyName,
    BangOlufsenTextHomeControlUri,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.SELECT,
]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Check if there are available options.
    if entry.options:
        entry.data = entry.options

    # If connection can't be made abort.
    if not await init_entities(hass, entry):
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.unique_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def init_entities(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialise the supported entities of the device."""
    client = MozartClient(host=entry.data[CONF_HOST])
    supports_battery = False
    model = entry.data[CONF_MODEL]

    # Check connection and try to initialize it.
    try:
        battery_state = client.get_battery_state(
            async_req=True, _request_timeout=3
        ).get()
    except MaxRetryError:
        _LOGGER.error("Unable to connect to %s", entry.data[CONF_NAME])
        return False

    # Get whether or not the device has a battery.
    if battery_state.battery_level > 0:
        supports_battery = True

    # Create the coordinator.
    coordinator = BangOlufsenCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Create the Binary Sensor entities.
    binary_sensors: list[BangOlufsenBinarySensor] = []

    if supports_battery:
        binary_sensors.append(BangOlufsenBinarySensorBatteryCharging(entry))

    # Check if device supports proxmity detection.
    if model in SupportEnum.PROXIMITY_SENSOR.value:
        binary_sensors.append(BangOlufsenBinarySensorProximity(entry))

    # Create the Number entities.
    numbers: list[BangOlufsenNumber] = [
        BangOlufsenNumberBass(entry),
        BangOlufsenNumberTreble(entry),
    ]

    # Get available favourites.
    favourites = client.get_presets(async_req=True).get()

    # Create the favourites Button entities.
    favourite_buttons: list[BangOlufsenButtonFavourite] = []

    for favourite_id in favourites:
        favourite_buttons.append(
            BangOlufsenButtonFavourite(entry, coordinator, favourites[favourite_id])
        )

    # Create the Sensor entities.
    sensors: list[BangOlufsenSensor] = [
        BangOlufsenSensorInputSignal(entry),
        BangOlufsenSensorMediaId(entry),
    ]

    if supports_battery:
        sensors.extend(
            [
                BangOlufsenSensorBatteryChargingTime(entry),
                BangOlufsenSensorBatteryLevel(entry),
                BangOlufsenSensorBatteryPlayingTime(entry),
            ]
        )

    # Create the Switch entities.
    switches: list[BangOlufsenSwitch] = [BangOlufsenSwitchLoudness(entry)]

    # Create the Text entities.
    beolink_self = client.get_beolink_self(async_req=True).get()

    texts: list[BangOlufsenText] = [
        BangOlufsenTextFriendlyName(entry, beolink_self.friendly_name),
    ]

    # Add the Home Control URI entity if the device supports it
    if model in SupportEnum.HOME_CONTROL.value:
        home_control = client.get_remote_home_control_uri(async_req=True).get()

        texts.append(BangOlufsenTextHomeControlUri(entry, home_control.uri))

    # Create the Select entities.
    selects: list[BangOlufsenSelect] = []

    # Create the listening position Select entity if supported
    scenes = client.get_all_scenes(async_req=True).get()

    # Listening positions
    for scene_key in scenes:
        scene = scenes[scene_key]

        if scene.tags is not None and "listeningposition" in scene.tags:
            selects.append(BangOlufsenSelectListeningPosition(entry))
            break

    # Create the sound mode select entity if supported
    # Currently the Balance does not expose any useful Sound Modes and should be excluded
    if model != ModelEnum.beosound_balance:
        listening_modes = client.get_listening_mode_set(async_req=True).get()
        if len(listening_modes) > 0:
            selects.append(BangOlufsenSelectSoundMode(entry))

    # Create the Media Player entity.
    media_player = BangOlufsenMediaPlayer(entry)

    # Add the created entities
    hass.data[DOMAIN][entry.unique_id] = {
        EntityEnum.BINARY_SENSORS: binary_sensors,
        EntityEnum.COORDINATOR: coordinator,
        EntityEnum.MEDIA_PLAYER: media_player,
        EntityEnum.NUMBERS: numbers,
        EntityEnum.FAVOURITES: favourite_buttons,
        EntityEnum.SENSORS: sensors,
        EntityEnum.SWITCHES: switches,
        EntityEnum.SELECTS: selects,
        EntityEnum.TEXT: texts,
    }

    # Start the WebSocket listener with a delay to allow for entity and dispatcher listener creation
    async_call_later(hass, 3.0, coordinator.connect_websocket)

    return True
