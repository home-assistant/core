"""Support for the Xiaomi vacuum cleaner robot."""
import asyncio
from functools import partial
import logging

from miio import DeviceException, Vacuum  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.components.vacuum import (
    ATTR_CLEANED_AREA,
    PLATFORM_SCHEMA,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    SUPPORT_BATTERY,
    SUPPORT_CLEAN_SPOT,
    SUPPORT_FAN_SPEED,
    SUPPORT_LOCATE,
    SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME,
    SUPPORT_SEND_COMMAND,
    SUPPORT_START,
    SUPPORT_STATE,
    SUPPORT_STOP,
    StateVacuumDevice,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_TOKEN,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_CLEAN_ZONE,
    SERVICE_MOVE_REMOTE_CONTROL,
    SERVICE_MOVE_REMOTE_CONTROL_STEP,
    SERVICE_START_REMOTE_CONTROL,
    SERVICE_STOP_REMOTE_CONTROL,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Vacuum cleaner"
DATA_KEY = "vacuum.xiaomi_miio"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

ATTR_CLEAN_START = "clean_start"
ATTR_CLEAN_STOP = "clean_stop"
ATTR_CLEANING_TIME = "cleaning_time"
ATTR_DO_NOT_DISTURB = "do_not_disturb"
ATTR_DO_NOT_DISTURB_START = "do_not_disturb_start"
ATTR_DO_NOT_DISTURB_END = "do_not_disturb_end"
ATTR_MAIN_BRUSH_LEFT = "main_brush_left"
ATTR_SIDE_BRUSH_LEFT = "side_brush_left"
ATTR_FILTER_LEFT = "filter_left"
ATTR_SENSOR_DIRTY_LEFT = "sensor_dirty_left"
ATTR_CLEANING_COUNT = "cleaning_count"
ATTR_CLEANED_TOTAL_AREA = "total_cleaned_area"
ATTR_CLEANING_TOTAL_TIME = "total_cleaning_time"
ATTR_ERROR = "error"
ATTR_RC_DURATION = "duration"
ATTR_RC_ROTATION = "rotation"
ATTR_RC_VELOCITY = "velocity"
ATTR_STATUS = "status"
ATTR_ZONE_ARRAY = "zone"
ATTR_ZONE_REPEATER = "repeats"

VACUUM_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids})

SERVICE_SCHEMA_REMOTE_CONTROL = VACUUM_SERVICE_SCHEMA.extend(
    {
        vol.Optional(ATTR_RC_VELOCITY): vol.All(
            vol.Coerce(float), vol.Clamp(min=-0.29, max=0.29)
        ),
        vol.Optional(ATTR_RC_ROTATION): vol.All(
            vol.Coerce(int), vol.Clamp(min=-179, max=179)
        ),
        vol.Optional(ATTR_RC_DURATION): cv.positive_int,
    }
)

SERVICE_SCHEMA_CLEAN_ZONE = VACUUM_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_ZONE_ARRAY): vol.All(
            list,
            [
                vol.ExactSequence(
                    [vol.Coerce(int), vol.Coerce(int), vol.Coerce(int), vol.Coerce(int)]
                )
            ],
        ),
        vol.Required(ATTR_ZONE_REPEATER): vol.All(
            vol.Coerce(int), vol.Clamp(min=1, max=3)
        ),
    }
)

SERVICE_SCHEMA_CLEAN_ZONE = VACUUM_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_ZONE_ARRAY): vol.All(
            list,
            [
                vol.ExactSequence(
                    [vol.Coerce(int), vol.Coerce(int), vol.Coerce(int), vol.Coerce(int)]
                )
            ],
        ),
        vol.Required(ATTR_ZONE_REPEATER): vol.All(
            vol.Coerce(int), vol.Clamp(min=1, max=3)
        ),
    }
)

SERVICE_TO_METHOD = {
    SERVICE_START_REMOTE_CONTROL: {"method": "async_remote_control_start"},
    SERVICE_STOP_REMOTE_CONTROL: {"method": "async_remote_control_stop"},
    SERVICE_MOVE_REMOTE_CONTROL: {
        "method": "async_remote_control_move",
        "schema": SERVICE_SCHEMA_REMOTE_CONTROL,
    },
    SERVICE_MOVE_REMOTE_CONTROL_STEP: {
        "method": "async_remote_control_move_step",
        "schema": SERVICE_SCHEMA_REMOTE_CONTROL,
    },
    SERVICE_CLEAN_ZONE: {
        "method": "async_clean_zone",
        "schema": SERVICE_SCHEMA_CLEAN_ZONE,
    },
}

SUPPORT_XIAOMI = (
    SUPPORT_STATE
    | SUPPORT_PAUSE
    | SUPPORT_STOP
    | SUPPORT_RETURN_HOME
    | SUPPORT_FAN_SPEED
    | SUPPORT_SEND_COMMAND
    | SUPPORT_LOCATE
    | SUPPORT_BATTERY
    | SUPPORT_CLEAN_SPOT
    | SUPPORT_START
)


STATE_CODE_TO_STATE = {
    2: STATE_IDLE,
    3: STATE_IDLE,
    5: STATE_CLEANING,
    6: STATE_RETURNING,
    7: STATE_CLEANING,
    8: STATE_DOCKED,
    9: STATE_ERROR,
    10: STATE_PAUSED,
    11: STATE_CLEANING,
    12: STATE_ERROR,
    15: STATE_RETURNING,
    16: STATE_CLEANING,
    17: STATE_CLEANING,
    18: STATE_CLEANING,
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Xiaomi vacuum cleaner robot platform."""
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config[CONF_HOST]
    token = config[CONF_TOKEN]
    name = config[CONF_NAME]

    # Create handler
    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])
    vacuum = Vacuum(host, token)

    mirobo = MiroboVacuum(name, vacuum)
    hass.data[DATA_KEY][host] = mirobo

    async_add_entities([mirobo], update_before_add=True)

    async def async_service_handler(service):
        """Map services to methods on MiroboVacuum."""
        method = SERVICE_TO_METHOD.get(service.service)
        params = {
            key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID
        }
        entity_ids = service.data.get(ATTR_ENTITY_ID)

        if entity_ids:
            target_vacuums = [
                vac
                for vac in hass.data[DATA_KEY].values()
                if vac.entity_id in entity_ids
            ]
        else:
            target_vacuums = hass.data[DATA_KEY].values()

        update_tasks = []
        for vacuum in target_vacuums:
            await getattr(vacuum, method["method"])(**params)

        for vacuum in target_vacuums:
            update_coro = vacuum.async_update_ha_state(True)
            update_tasks.append(update_coro)

        if update_tasks:
            await asyncio.wait(update_tasks)

    for vacuum_service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[vacuum_service].get("schema", VACUUM_SERVICE_SCHEMA)
        hass.services.async_register(
            DOMAIN, vacuum_service, async_service_handler, schema=schema
        )


class MiroboVacuum(StateVacuumDevice):
    """Representation of a Xiaomi Vacuum cleaner robot."""

    def __init__(self, name, vacuum):
        """Initialize the Xiaomi vacuum cleaner robot handler."""
        self._name = name
        self._vacuum = vacuum

        self.vacuum_state = None
        self._available = False

        self.consumable_state = None
        self.clean_history = None
        self.dnd_state = None
        self.last_clean = None
        self._fan_speeds = None
        self._fan_speeds_reverse = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the status of the vacuum cleaner."""
        if self.vacuum_state is not None:
            # The vacuum reverts back to an idle state after erroring out.
            # We want to keep returning an error until it has been cleared.
            if self.vacuum_state.got_error:
                return STATE_ERROR
            try:
                return STATE_CODE_TO_STATE[int(self.vacuum_state.state_code)]
            except KeyError:
                _LOGGER.error(
                    "STATE not supported: %s, state_code: %s",
                    self.vacuum_state.state,
                    self.vacuum_state.state_code,
                )
                return None

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        if self.vacuum_state is not None:
            return self.vacuum_state.battery

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        if self.vacuum_state is not None:
            speed = self.vacuum_state.fanspeed
            if speed in self._fan_speeds_reverse:
                return self._fan_speeds_reverse[speed]

            _LOGGER.debug("Unable to find reverse for %s", speed)

            return speed

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return list(self._fan_speeds)

    @property
    def device_state_attributes(self):
        """Return the specific state attributes of this vacuum cleaner."""
        attrs = {}
        if self.vacuum_state is not None:
            attrs.update(
                {
                    ATTR_DO_NOT_DISTURB: STATE_ON
                    if self.dnd_state.enabled
                    else STATE_OFF,
                    ATTR_DO_NOT_DISTURB_START: str(self.dnd_state.start),
                    ATTR_DO_NOT_DISTURB_END: str(self.dnd_state.end),
                    # Not working --> 'Cleaning mode':
                    #    STATE_ON if self.vacuum_state.in_cleaning else STATE_OFF,
                    ATTR_CLEANING_TIME: int(
                        self.vacuum_state.clean_time.total_seconds() / 60
                    ),
                    ATTR_CLEANED_AREA: int(self.vacuum_state.clean_area),
                    ATTR_CLEANING_COUNT: int(self.clean_history.count),
                    ATTR_CLEANED_TOTAL_AREA: int(self.clean_history.total_area),
                    ATTR_CLEANING_TOTAL_TIME: int(
                        self.clean_history.total_duration.total_seconds() / 60
                    ),
                    ATTR_MAIN_BRUSH_LEFT: int(
                        self.consumable_state.main_brush_left.total_seconds() / 3600
                    ),
                    ATTR_SIDE_BRUSH_LEFT: int(
                        self.consumable_state.side_brush_left.total_seconds() / 3600
                    ),
                    ATTR_FILTER_LEFT: int(
                        self.consumable_state.filter_left.total_seconds() / 3600
                    ),
                    ATTR_SENSOR_DIRTY_LEFT: int(
                        self.consumable_state.sensor_dirty_left.total_seconds() / 3600
                    ),
                    ATTR_STATUS: str(self.vacuum_state.state),
                }
            )

            if self.last_clean:
                attrs[ATTR_CLEAN_START] = self.last_clean.start
                attrs[ATTR_CLEAN_STOP] = self.last_clean.end

            if self.vacuum_state.got_error:
                attrs[ATTR_ERROR] = self.vacuum_state.error
        return attrs

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_XIAOMI

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a vacuum command handling error messages."""
        try:
            await self.hass.async_add_executor_job(partial(func, *args, **kwargs))
            return True
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    async def async_start(self):
        """Start or resume the cleaning task."""
        await self._try_command(
            "Unable to start the vacuum: %s", self._vacuum.resume_or_start
        )

    async def async_pause(self):
        """Pause the cleaning task."""
        await self._try_command("Unable to set start/pause: %s", self._vacuum.pause)

    async def async_stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        await self._try_command("Unable to stop: %s", self._vacuum.stop)

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if fan_speed in self._fan_speeds:
            fan_speed = self._fan_speeds[fan_speed]
        else:
            try:
                fan_speed = int(fan_speed)
            except ValueError as exc:
                _LOGGER.error(
                    "Fan speed step not recognized (%s). Valid speeds are: %s",
                    exc,
                    self.fan_speed_list,
                )
                return
        await self._try_command(
            "Unable to set fan speed: %s", self._vacuum.set_fan_speed, fan_speed
        )

    async def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        await self._try_command("Unable to return home: %s", self._vacuum.home)

    async def async_clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        await self._try_command(
            "Unable to start the vacuum for a spot clean-up: %s", self._vacuum.spot
        )

    async def async_locate(self, **kwargs):
        """Locate the vacuum cleaner."""
        await self._try_command("Unable to locate the botvac: %s", self._vacuum.find)

    async def async_send_command(self, command, params=None, **kwargs):
        """Send raw command."""
        await self._try_command(
            "Unable to send command to the vacuum: %s",
            self._vacuum.raw_command,
            command,
            params,
        )

    async def async_remote_control_start(self):
        """Start remote control mode."""
        await self._try_command(
            "Unable to start remote control the vacuum: %s", self._vacuum.manual_start
        )

    async def async_remote_control_stop(self):
        """Stop remote control mode."""
        await self._try_command(
            "Unable to stop remote control the vacuum: %s", self._vacuum.manual_stop
        )

    async def async_remote_control_move(
        self, rotation: int = 0, velocity: float = 0.3, duration: int = 1500
    ):
        """Move vacuum with remote control mode."""
        await self._try_command(
            "Unable to move with remote control the vacuum: %s",
            self._vacuum.manual_control,
            velocity=velocity,
            rotation=rotation,
            duration=duration,
        )

    async def async_remote_control_move_step(
        self, rotation: int = 0, velocity: float = 0.2, duration: int = 1500
    ):
        """Move vacuum one step with remote control mode."""
        await self._try_command(
            "Unable to remote control the vacuum: %s",
            self._vacuum.manual_control_once,
            velocity=velocity,
            rotation=rotation,
            duration=duration,
        )

    def update(self):
        """Fetch state from the device."""
        try:
            state = self._vacuum.status()
            self.vacuum_state = state

            self._fan_speeds = self._vacuum.fan_speed_presets()
            self._fan_speeds_reverse = {v: k for k, v in self._fan_speeds.items()}

            self.consumable_state = self._vacuum.consumable_status()
            self.clean_history = self._vacuum.clean_history()
            self.last_clean = self._vacuum.last_clean_details()
            self.dnd_state = self._vacuum.dnd_status()

            self._available = True
        except OSError as exc:
            _LOGGER.error("Got OSError while fetching the state: %s", exc)
        except DeviceException as exc:
            _LOGGER.warning("Got exception while fetching the state: %s", exc)

    async def async_clean_zone(self, zone, repeats=1):
        """Clean selected area for the number of repeats indicated."""
        for _zone in zone:
            _zone.append(repeats)
        _LOGGER.debug("Zone with repeats: %s", zone)
        try:
            await self.hass.async_add_executor_job(self._vacuum.zoned_clean, zone)
        except (OSError, DeviceException) as exc:
            _LOGGER.error("Unable to send zoned_clean command to the vacuum: %s", exc)
