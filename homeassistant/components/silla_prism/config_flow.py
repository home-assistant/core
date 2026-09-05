"""Silla Prism for Home Assistant."""

import asyncio
import logging
import re
from typing import Any, override

from pysillaprism import parse_hello, parse_message
from pysillaprism.exceptions import PrismParseError
import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.mqtt import ReceiveMessage, async_wait_for_mqtt_client
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import (
    CONF_BATTERY_DISCHARGE_POSITIVE,
    CONF_BATTERY_MAX_CHARGE_POWER,
    CONF_BATTERY_POWER_SENSOR,
    CONF_BATTERY_SOC_SENSOR,
    CONF_HOME_LOAD_INCLUDES_EV,
    CONF_HOME_LOAD_POWER_SENSOR,
    CONF_MAX_CURRENT,
    CONF_PORTS,
    CONF_POWERWALL,
    CONF_SERIAL,
    CONF_SOLAR_BALANCE_DEADBAND_POWER,
    CONF_SOLAR_BALANCE_DECREASE_STEP,
    CONF_SOLAR_BALANCE_DRY_RUN,
    CONF_SOLAR_BALANCE_HIGH_RESERVE_POWER,
    CONF_SOLAR_BALANCE_INCREASE_INTERVAL,
    CONF_SOLAR_BALANCE_INCREASE_STEP,
    CONF_SOLAR_BALANCE_MID_RESERVE_POWER,
    CONF_SOLAR_BALANCE_PHASES,
    CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY,
    CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER,
    CONF_SOLAR_BALANCE_SOC_HIGH,
    CONF_SOLAR_BALANCE_SOC_MID,
    CONF_SOLAR_BALANCE_START_DELAY,
    CONF_SOLAR_BALANCE_TARGET_EXPORT_POWER,
    CONF_SOLAR_BALANCE_USE_BATTERY_CHARGE,
    CONF_SOLAR_BATTERY_BALANCE,
    CONF_SOLAR_PRODUCTION_POWER_SENSOR,
    CONF_TOPIC,
    CONF_VSENSORS,
    DEFAULT_BATTERY_DISCHARGE_POSITIVE,
    DEFAULT_BATTERY_MAX_CHARGE_POWER,
    DEFAULT_BATTERY_POWER_SENSOR,
    DEFAULT_BATTERY_SOC_SENSOR,
    DEFAULT_HOME_LOAD_INCLUDES_EV,
    DEFAULT_HOME_LOAD_POWER_SENSOR,
    DEFAULT_MAX_CURRENT,
    DEFAULT_PORTS,
    DEFAULT_POWERWALL,
    DEFAULT_SERIAL,
    DEFAULT_SOLAR_BALANCE_DEADBAND_POWER,
    DEFAULT_SOLAR_BALANCE_DECREASE_STEP,
    DEFAULT_SOLAR_BALANCE_DRY_RUN,
    DEFAULT_SOLAR_BALANCE_HIGH_RESERVE_POWER,
    DEFAULT_SOLAR_BALANCE_INCREASE_INTERVAL,
    DEFAULT_SOLAR_BALANCE_INCREASE_STEP,
    DEFAULT_SOLAR_BALANCE_MID_RESERVE_POWER,
    DEFAULT_SOLAR_BALANCE_PHASES,
    DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY,
    DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER,
    DEFAULT_SOLAR_BALANCE_SOC_HIGH,
    DEFAULT_SOLAR_BALANCE_SOC_MID,
    DEFAULT_SOLAR_BALANCE_START_DELAY,
    DEFAULT_SOLAR_BALANCE_TARGET_EXPORT_POWER,
    DEFAULT_SOLAR_BALANCE_USE_BATTERY_CHARGE,
    DEFAULT_SOLAR_BATTERY_BALANCE,
    DEFAULT_SOLAR_PRODUCTION_POWER_SENSOR,
    DEFAULT_TOPIC,
    DEFAULT_VSENSORS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_PROBE_TIMEOUT = 5
type ConfigValue = bool | int | str | None

BATTERY_SENSOR_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor")
)

SILLA_PRISM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOPIC, default=DEFAULT_TOPIC): cv.string,
        vol.Required(CONF_PORTS, default=DEFAULT_PORTS): cv.positive_int,
        vol.Optional(CONF_SERIAL, default=DEFAULT_SERIAL): cv.string,
        vol.Optional(CONF_VSENSORS, default=DEFAULT_VSENSORS): cv.boolean,
        vol.Optional(CONF_POWERWALL, default=DEFAULT_POWERWALL): cv.boolean,
        vol.Optional(CONF_MAX_CURRENT, default=DEFAULT_MAX_CURRENT): cv.positive_int,
        vol.Optional(
            CONF_SOLAR_BATTERY_BALANCE, default=DEFAULT_SOLAR_BATTERY_BALANCE
        ): cv.boolean,
        vol.Optional(CONF_BATTERY_POWER_SENSOR): BATTERY_SENSOR_SELECTOR,
        vol.Optional(CONF_SOLAR_PRODUCTION_POWER_SENSOR): BATTERY_SENSOR_SELECTOR,
        vol.Optional(CONF_HOME_LOAD_POWER_SENSOR): BATTERY_SENSOR_SELECTOR,
        vol.Optional(
            CONF_HOME_LOAD_INCLUDES_EV, default=DEFAULT_HOME_LOAD_INCLUDES_EV
        ): cv.boolean,
        vol.Optional(CONF_BATTERY_SOC_SENSOR): BATTERY_SENSOR_SELECTOR,
        vol.Optional(
            CONF_BATTERY_DISCHARGE_POSITIVE,
            default=DEFAULT_BATTERY_DISCHARGE_POSITIVE,
        ): cv.boolean,
        vol.Optional(
            CONF_BATTERY_MAX_CHARGE_POWER, default=DEFAULT_BATTERY_MAX_CHARGE_POWER
        ): cv.positive_int,
        vol.Optional(
            CONF_SOLAR_BALANCE_PHASES, default=DEFAULT_SOLAR_BALANCE_PHASES
        ): vol.In([1, 3]),
        vol.Optional(
            CONF_SOLAR_BALANCE_START_DELAY,
            default=DEFAULT_SOLAR_BALANCE_START_DELAY,
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
        vol.Optional(
            CONF_SOLAR_BALANCE_USE_BATTERY_CHARGE,
            default=DEFAULT_SOLAR_BALANCE_USE_BATTERY_CHARGE,
        ): cv.boolean,
        vol.Optional(
            CONF_SOLAR_BALANCE_SOC_MID, default=DEFAULT_SOLAR_BALANCE_SOC_MID
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional(
            CONF_SOLAR_BALANCE_SOC_HIGH, default=DEFAULT_SOLAR_BALANCE_SOC_HIGH
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional(
            CONF_SOLAR_BALANCE_MID_RESERVE_POWER,
            default=DEFAULT_SOLAR_BALANCE_MID_RESERVE_POWER,
        ): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(
            CONF_SOLAR_BALANCE_HIGH_RESERVE_POWER,
            default=DEFAULT_SOLAR_BALANCE_HIGH_RESERVE_POWER,
        ): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(
            CONF_SOLAR_BALANCE_TARGET_EXPORT_POWER,
            default=DEFAULT_SOLAR_BALANCE_TARGET_EXPORT_POWER,
        ): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(
            CONF_SOLAR_BALANCE_DEADBAND_POWER,
            default=DEFAULT_SOLAR_BALANCE_DEADBAND_POWER,
        ): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(
            CONF_SOLAR_BALANCE_INCREASE_INTERVAL,
            default=DEFAULT_SOLAR_BALANCE_INCREASE_INTERVAL,
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=300)),
        vol.Optional(
            CONF_SOLAR_BALANCE_INCREASE_STEP,
            default=DEFAULT_SOLAR_BALANCE_INCREASE_STEP,
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
        vol.Optional(
            CONF_SOLAR_BALANCE_DECREASE_STEP,
            default=DEFAULT_SOLAR_BALANCE_DECREASE_STEP,
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
        vol.Optional(
            CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER,
            default=DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER,
        ): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(
            CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY,
            default=DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY,
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=600)),
        vol.Optional(
            CONF_SOLAR_BALANCE_DRY_RUN,
            default=DEFAULT_SOLAR_BALANCE_DRY_RUN,
        ): cv.boolean,
    }
)


class PrismConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Silla Prism config flow."""

    VERSION = 1
    MINOR_VERSION = 10

    def __init__(self) -> None:
        """Initialize flow."""
        self._topic: str | None = DEFAULT_TOPIC
        self._ports: int = DEFAULT_PORTS
        self._vsensors: bool = DEFAULT_VSENSORS
        self._powerwall: bool = DEFAULT_POWERWALL
        self._serial: str = DEFAULT_SERIAL
        self._max_current: int = DEFAULT_MAX_CURRENT
        self._solar_battery_balance: bool = DEFAULT_SOLAR_BATTERY_BALANCE
        self._battery_power_sensor: str = DEFAULT_BATTERY_POWER_SENSOR
        self._solar_production_power_sensor: str = DEFAULT_SOLAR_PRODUCTION_POWER_SENSOR
        self._home_load_power_sensor: str = DEFAULT_HOME_LOAD_POWER_SENSOR
        self._home_load_includes_ev: bool = DEFAULT_HOME_LOAD_INCLUDES_EV
        self._battery_discharge_positive: bool = DEFAULT_BATTERY_DISCHARGE_POSITIVE
        self._battery_max_charge_power: int = DEFAULT_BATTERY_MAX_CHARGE_POWER
        self._solar_balance_phases: int = DEFAULT_SOLAR_BALANCE_PHASES
        self._solar_balance_start_delay: int = DEFAULT_SOLAR_BALANCE_START_DELAY
        self._solar_balance_use_battery_charge: bool = (
            DEFAULT_SOLAR_BALANCE_USE_BATTERY_CHARGE
        )
        self._battery_soc_sensor: str = DEFAULT_BATTERY_SOC_SENSOR
        self._solar_balance_soc_mid: int = DEFAULT_SOLAR_BALANCE_SOC_MID
        self._solar_balance_soc_high: int = DEFAULT_SOLAR_BALANCE_SOC_HIGH
        self._solar_balance_mid_reserve_power: int = (
            DEFAULT_SOLAR_BALANCE_MID_RESERVE_POWER
        )
        self._solar_balance_high_reserve_power: int = (
            DEFAULT_SOLAR_BALANCE_HIGH_RESERVE_POWER
        )
        self._solar_balance_target_export_power: int = (
            DEFAULT_SOLAR_BALANCE_TARGET_EXPORT_POWER
        )
        self._solar_balance_deadband_power: int = DEFAULT_SOLAR_BALANCE_DEADBAND_POWER
        self._solar_balance_increase_interval: int = (
            DEFAULT_SOLAR_BALANCE_INCREASE_INTERVAL
        )
        self._solar_balance_increase_step: int = DEFAULT_SOLAR_BALANCE_INCREASE_STEP
        self._solar_balance_decrease_step: int = DEFAULT_SOLAR_BALANCE_DECREASE_STEP
        self._solar_balance_residual_export_power: int = (
            DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER
        )
        self._solar_balance_residual_export_delay: int = (
            DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY
        )
        self._solar_balance_dry_run: bool = DEFAULT_SOLAR_BALANCE_DRY_RUN
        self._discovered_serial: str = ""

    async def fetch_device_info(self) -> str | None:
        """Fetch information from MQTT."""
        assert self._topic is not None
        if await self._async_probe(self._topic):
            return None
        return "no_device"

    async def _async_probe(self, base_topic: str) -> bool:
        """Return True if a recognizable Prism message is seen under the base topic."""
        normalized_topic = base_topic.strip().strip("/")
        seen = asyncio.Event()

        @callback
        def _message(msg: ReceiveMessage) -> None:
            if isinstance(msg.payload, str) and (
                parse_message(normalized_topic, msg.topic, msg.payload) is not None
            ):
                seen.set()

        unsubscribe = await mqtt.async_subscribe(
            self.hass, f"{normalized_topic}/#", _message
        )
        try:
            await asyncio.wait_for(seen.wait(), _PROBE_TIMEOUT)
        except TimeoutError:
            return False
        finally:
            unsubscribe()
        return True

    async def _async_validate_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        _LOGGER.debug("Called with user input: %s source: %s", user_input, self.source)

        assert user_input is not None

        normalized_topic = user_input[CONF_TOPIC].strip().strip("/")
        if not normalized_topic:
            return self.async_show_form(
                step_id="user",
                data_schema=SILLA_PRISM_SCHEMA,
                errors={CONF_TOPIC: "invalid_base_topic"},
            )
        try:
            mqtt.valid_publish_topic(normalized_topic)
        except vol.Invalid:
            return self.async_show_form(
                step_id="user",
                data_schema=SILLA_PRISM_SCHEMA,
                errors={CONF_TOPIC: "invalid_base_topic"},
            )

        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            self._ports = entry.data.get(CONF_PORTS, DEFAULT_PORTS)
            self._serial = entry.data.get(CONF_SERIAL, DEFAULT_SERIAL)
            self._vsensors = entry.data.get(CONF_VSENSORS, DEFAULT_VSENSORS)
            self._powerwall = entry.data.get(CONF_POWERWALL, DEFAULT_POWERWALL)
        else:
            self._ports = user_input.get(CONF_PORTS, DEFAULT_PORTS)
            self._serial = re.sub(
                r"[^a-zA-Z0-9]", "", user_input.get(CONF_SERIAL, DEFAULT_SERIAL)
            )
            self._vsensors = user_input.get(CONF_VSENSORS, DEFAULT_VSENSORS)
            self._powerwall = user_input.get(CONF_POWERWALL, DEFAULT_POWERWALL)

        self._topic = normalized_topic
        self._max_current = max(
            min(user_input.get(CONF_MAX_CURRENT, DEFAULT_MAX_CURRENT), 32), 6
        )  # clamp between 6 and 32
        self._solar_battery_balance = user_input.get(
            CONF_SOLAR_BATTERY_BALANCE, DEFAULT_SOLAR_BATTERY_BALANCE
        )
        self._battery_power_sensor = user_input.get(
            CONF_BATTERY_POWER_SENSOR, DEFAULT_BATTERY_POWER_SENSOR
        ).strip()
        self._solar_production_power_sensor = user_input.get(
            CONF_SOLAR_PRODUCTION_POWER_SENSOR,
            DEFAULT_SOLAR_PRODUCTION_POWER_SENSOR,
        ).strip()
        self._home_load_power_sensor = user_input.get(
            CONF_HOME_LOAD_POWER_SENSOR, DEFAULT_HOME_LOAD_POWER_SENSOR
        ).strip()
        self._home_load_includes_ev = user_input.get(
            CONF_HOME_LOAD_INCLUDES_EV, DEFAULT_HOME_LOAD_INCLUDES_EV
        )
        self._battery_soc_sensor = user_input.get(
            CONF_BATTERY_SOC_SENSOR, DEFAULT_BATTERY_SOC_SENSOR
        ).strip()
        self._battery_discharge_positive = user_input.get(
            CONF_BATTERY_DISCHARGE_POSITIVE, DEFAULT_BATTERY_DISCHARGE_POSITIVE
        )
        self._battery_max_charge_power = user_input.get(
            CONF_BATTERY_MAX_CHARGE_POWER, DEFAULT_BATTERY_MAX_CHARGE_POWER
        )
        self._solar_balance_phases = user_input.get(
            CONF_SOLAR_BALANCE_PHASES, DEFAULT_SOLAR_BALANCE_PHASES
        )
        self._solar_balance_start_delay = user_input.get(
            CONF_SOLAR_BALANCE_START_DELAY, DEFAULT_SOLAR_BALANCE_START_DELAY
        )
        self._solar_balance_use_battery_charge = user_input.get(
            CONF_SOLAR_BALANCE_USE_BATTERY_CHARGE,
            DEFAULT_SOLAR_BALANCE_USE_BATTERY_CHARGE,
        )
        self._solar_balance_soc_mid = user_input.get(
            CONF_SOLAR_BALANCE_SOC_MID, DEFAULT_SOLAR_BALANCE_SOC_MID
        )
        self._solar_balance_soc_high = user_input.get(
            CONF_SOLAR_BALANCE_SOC_HIGH, DEFAULT_SOLAR_BALANCE_SOC_HIGH
        )
        self._solar_balance_mid_reserve_power = user_input.get(
            CONF_SOLAR_BALANCE_MID_RESERVE_POWER,
            DEFAULT_SOLAR_BALANCE_MID_RESERVE_POWER,
        )
        self._solar_balance_high_reserve_power = user_input.get(
            CONF_SOLAR_BALANCE_HIGH_RESERVE_POWER,
            DEFAULT_SOLAR_BALANCE_HIGH_RESERVE_POWER,
        )
        self._solar_balance_target_export_power = user_input.get(
            CONF_SOLAR_BALANCE_TARGET_EXPORT_POWER,
            DEFAULT_SOLAR_BALANCE_TARGET_EXPORT_POWER,
        )
        self._solar_balance_deadband_power = user_input.get(
            CONF_SOLAR_BALANCE_DEADBAND_POWER,
            DEFAULT_SOLAR_BALANCE_DEADBAND_POWER,
        )
        self._solar_balance_increase_interval = user_input.get(
            CONF_SOLAR_BALANCE_INCREASE_INTERVAL,
            DEFAULT_SOLAR_BALANCE_INCREASE_INTERVAL,
        )
        self._solar_balance_increase_step = user_input.get(
            CONF_SOLAR_BALANCE_INCREASE_STEP,
            DEFAULT_SOLAR_BALANCE_INCREASE_STEP,
        )
        self._solar_balance_decrease_step = user_input.get(
            CONF_SOLAR_BALANCE_DECREASE_STEP,
            DEFAULT_SOLAR_BALANCE_DECREASE_STEP,
        )
        self._solar_balance_residual_export_power = user_input.get(
            CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER,
            DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER,
        )
        self._solar_balance_residual_export_delay = user_input.get(
            CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY,
            DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY,
        )
        self._solar_balance_dry_run = user_input.get(
            CONF_SOLAR_BALANCE_DRY_RUN,
            DEFAULT_SOLAR_BALANCE_DRY_RUN,
        )
        if self.source != SOURCE_RECONFIGURE:
            await self.async_set_unique_id(self._topic)
            self._abort_if_unique_id_configured()

        if self._solar_balance_soc_mid > self._solar_balance_soc_high:
            (
                self._solar_balance_soc_mid,
                self._solar_balance_soc_high,
            ) = (
                self._solar_balance_soc_high,
                self._solar_balance_soc_mid,
            )

        if self._solar_battery_balance and self._battery_power_sensor == "":
            return await self._async_step_user_base(error="battery_sensor_required")
        if (
            self._solar_battery_balance
            and self._home_load_power_sensor != ""
            and self._solar_production_power_sensor == ""
        ):
            return await self._async_step_user_base(error="solar_sensor_required")

        return await self._async_try_fetch_device_info()

    async def _async_step_user_base(
        self, user_input: dict[str, Any] | None = None, error: str | None = None
    ) -> ConfigFlowResult:
        _LOGGER.info("Async_step_user %s", DOMAIN)
        if user_input is not None:
            return await self._async_validate_device(user_input)

        errors = {}
        if error is not None:
            errors["base"] = error

        if self.source == SOURCE_RECONFIGURE:
            # We are reconfiguring an existing device
            entry = self._get_reconfigure_entry()
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_TOPIC, default=entry.data[CONF_TOPIC]
                        ): cv.string,
                        vol.Optional(
                            CONF_MAX_CURRENT,
                            default=entry.data.get(
                                CONF_MAX_CURRENT, DEFAULT_MAX_CURRENT
                            ),
                        ): cv.positive_int,
                        vol.Optional(
                            CONF_SOLAR_BATTERY_BALANCE,
                            default=entry.data.get(
                                CONF_SOLAR_BATTERY_BALANCE,
                                DEFAULT_SOLAR_BATTERY_BALANCE,
                            ),
                        ): cv.boolean,
                        vol.Optional(
                            CONF_BATTERY_POWER_SENSOR,
                            default=entry.data.get(
                                CONF_BATTERY_POWER_SENSOR,
                                DEFAULT_BATTERY_POWER_SENSOR,
                            ),
                        ): BATTERY_SENSOR_SELECTOR,
                        vol.Optional(
                            CONF_SOLAR_PRODUCTION_POWER_SENSOR,
                            default=entry.data.get(
                                CONF_SOLAR_PRODUCTION_POWER_SENSOR,
                                DEFAULT_SOLAR_PRODUCTION_POWER_SENSOR,
                            ),
                        ): BATTERY_SENSOR_SELECTOR,
                        vol.Optional(
                            CONF_HOME_LOAD_POWER_SENSOR,
                            default=entry.data.get(
                                CONF_HOME_LOAD_POWER_SENSOR,
                                DEFAULT_HOME_LOAD_POWER_SENSOR,
                            ),
                        ): BATTERY_SENSOR_SELECTOR,
                        vol.Optional(
                            CONF_HOME_LOAD_INCLUDES_EV,
                            default=entry.data.get(
                                CONF_HOME_LOAD_INCLUDES_EV,
                                DEFAULT_HOME_LOAD_INCLUDES_EV,
                            ),
                        ): cv.boolean,
                        vol.Optional(
                            CONF_BATTERY_SOC_SENSOR,
                            default=entry.data.get(
                                CONF_BATTERY_SOC_SENSOR,
                                DEFAULT_BATTERY_SOC_SENSOR,
                            ),
                        ): BATTERY_SENSOR_SELECTOR,
                        vol.Optional(
                            CONF_BATTERY_DISCHARGE_POSITIVE,
                            default=entry.data.get(
                                CONF_BATTERY_DISCHARGE_POSITIVE,
                                DEFAULT_BATTERY_DISCHARGE_POSITIVE,
                            ),
                        ): cv.boolean,
                        vol.Optional(
                            CONF_BATTERY_MAX_CHARGE_POWER,
                            default=entry.data.get(
                                CONF_BATTERY_MAX_CHARGE_POWER,
                                DEFAULT_BATTERY_MAX_CHARGE_POWER,
                            ),
                        ): cv.positive_int,
                        vol.Optional(
                            CONF_SOLAR_BALANCE_PHASES,
                            default=entry.data.get(
                                CONF_SOLAR_BALANCE_PHASES,
                                DEFAULT_SOLAR_BALANCE_PHASES,
                            ),
                        ): vol.In([1, 3]),
                        vol.Optional(
                            CONF_SOLAR_BALANCE_START_DELAY,
                            default=entry.data.get(
                                CONF_SOLAR_BALANCE_START_DELAY,
                                DEFAULT_SOLAR_BALANCE_START_DELAY,
                            ),
                        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
                        vol.Optional(
                            CONF_SOLAR_BALANCE_USE_BATTERY_CHARGE,
                            default=entry.data.get(
                                CONF_SOLAR_BALANCE_USE_BATTERY_CHARGE,
                                DEFAULT_SOLAR_BALANCE_USE_BATTERY_CHARGE,
                            ),
                        ): cv.boolean,
                        vol.Optional(
                            CONF_SOLAR_BALANCE_SOC_MID,
                            default=entry.data.get(
                                CONF_SOLAR_BALANCE_SOC_MID,
                                DEFAULT_SOLAR_BALANCE_SOC_MID,
                            ),
                        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                        vol.Optional(
                            CONF_SOLAR_BALANCE_SOC_HIGH,
                            default=entry.data.get(
                                CONF_SOLAR_BALANCE_SOC_HIGH,
                                DEFAULT_SOLAR_BALANCE_SOC_HIGH,
                            ),
                        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                        vol.Optional(
                            CONF_SOLAR_BALANCE_MID_RESERVE_POWER,
                            default=entry.data.get(
                                CONF_SOLAR_BALANCE_MID_RESERVE_POWER,
                                DEFAULT_SOLAR_BALANCE_MID_RESERVE_POWER,
                            ),
                        ): vol.All(vol.Coerce(int), vol.Range(min=0)),
                        vol.Optional(
                            CONF_SOLAR_BALANCE_HIGH_RESERVE_POWER,
                            default=entry.data.get(
                                CONF_SOLAR_BALANCE_HIGH_RESERVE_POWER,
                                DEFAULT_SOLAR_BALANCE_HIGH_RESERVE_POWER,
                            ),
                        ): vol.All(vol.Coerce(int), vol.Range(min=0)),
                        vol.Optional(
                            CONF_SOLAR_BALANCE_TARGET_EXPORT_POWER,
                            default=entry.data.get(
                                CONF_SOLAR_BALANCE_TARGET_EXPORT_POWER,
                                DEFAULT_SOLAR_BALANCE_TARGET_EXPORT_POWER,
                            ),
                        ): vol.All(vol.Coerce(int), vol.Range(min=0)),
                        vol.Optional(
                            CONF_SOLAR_BALANCE_DEADBAND_POWER,
                            default=entry.data.get(
                                CONF_SOLAR_BALANCE_DEADBAND_POWER,
                                DEFAULT_SOLAR_BALANCE_DEADBAND_POWER,
                            ),
                        ): vol.All(vol.Coerce(int), vol.Range(min=0)),
                        vol.Optional(
                            CONF_SOLAR_BALANCE_INCREASE_INTERVAL,
                            default=entry.data.get(
                                CONF_SOLAR_BALANCE_INCREASE_INTERVAL,
                                DEFAULT_SOLAR_BALANCE_INCREASE_INTERVAL,
                            ),
                        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=300)),
                        vol.Optional(
                            CONF_SOLAR_BALANCE_INCREASE_STEP,
                            default=entry.data.get(
                                CONF_SOLAR_BALANCE_INCREASE_STEP,
                                DEFAULT_SOLAR_BALANCE_INCREASE_STEP,
                            ),
                        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                        vol.Optional(
                            CONF_SOLAR_BALANCE_DECREASE_STEP,
                            default=entry.data.get(
                                CONF_SOLAR_BALANCE_DECREASE_STEP,
                                DEFAULT_SOLAR_BALANCE_DECREASE_STEP,
                            ),
                        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                        vol.Optional(
                            CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER,
                            default=entry.data.get(
                                CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER,
                                DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER,
                            ),
                        ): vol.All(vol.Coerce(int), vol.Range(min=0)),
                        vol.Optional(
                            CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY,
                            default=entry.data.get(
                                CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY,
                                DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY,
                            ),
                        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=600)),
                        vol.Optional(
                            CONF_SOLAR_BALANCE_DRY_RUN,
                            default=entry.data.get(
                                CONF_SOLAR_BALANCE_DRY_RUN,
                                DEFAULT_SOLAR_BALANCE_DRY_RUN,
                            ),
                        ): cv.boolean,
                    }
                ),
                errors=errors,
            )
        # We are creating a new device
        return self.async_show_form(
            step_id="user",
            data_schema=SILLA_PRISM_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        if user_input is not None:
            return await self._async_validate_device(user_input)

        return await self._async_step_user_base()

    async def _async_try_fetch_device_info(self) -> ConfigFlowResult:
        """Try to fetch device info and return any errors."""
        error = None

        # Make sure MQTT integration is enabled and the client is available
        if not await async_wait_for_mqtt_client(self.hass):
            if self.source != SOURCE_RECONFIGURE:
                return self.async_abort(reason="mqtt_unavailable")
            error = "mqtt_unavailable"
            _LOGGER.error("MQTT integration is not available")

        if error is None:
            error = await self.fetch_device_info()

        if error is None:
            if self.source == SOURCE_RECONFIGURE:
                return await self._async_update_entry()
            return await self._async_create_entry()

        if self.source == SOURCE_RECONFIGURE:
            return await self.async_step_reconfigure()
        return await self._async_step_user_base(error=error)

    async def _async_create_entry(self) -> ConfigFlowResult:
        config_data: dict[str, ConfigValue] = {
            CONF_TOPIC: self._topic,
        }
        optional_data: dict[str, tuple[ConfigValue, ConfigValue]] = {
            CONF_PORTS: (self._ports, DEFAULT_PORTS),
            CONF_SERIAL: (self._serial, DEFAULT_SERIAL),
            CONF_VSENSORS: (self._vsensors, DEFAULT_VSENSORS),
            CONF_POWERWALL: (self._powerwall, DEFAULT_POWERWALL),
            CONF_MAX_CURRENT: (self._max_current, DEFAULT_MAX_CURRENT),
            CONF_SOLAR_BATTERY_BALANCE: (
                self._solar_battery_balance,
                DEFAULT_SOLAR_BATTERY_BALANCE,
            ),
            CONF_BATTERY_POWER_SENSOR: (
                self._battery_power_sensor,
                DEFAULT_BATTERY_POWER_SENSOR,
            ),
            CONF_SOLAR_PRODUCTION_POWER_SENSOR: (
                self._solar_production_power_sensor,
                DEFAULT_SOLAR_PRODUCTION_POWER_SENSOR,
            ),
            CONF_HOME_LOAD_POWER_SENSOR: (
                self._home_load_power_sensor,
                DEFAULT_HOME_LOAD_POWER_SENSOR,
            ),
            CONF_HOME_LOAD_INCLUDES_EV: (
                self._home_load_includes_ev,
                DEFAULT_HOME_LOAD_INCLUDES_EV,
            ),
            CONF_BATTERY_SOC_SENSOR: (
                self._battery_soc_sensor,
                DEFAULT_BATTERY_SOC_SENSOR,
            ),
            CONF_BATTERY_DISCHARGE_POSITIVE: (
                self._battery_discharge_positive,
                DEFAULT_BATTERY_DISCHARGE_POSITIVE,
            ),
            CONF_BATTERY_MAX_CHARGE_POWER: (
                self._battery_max_charge_power,
                DEFAULT_BATTERY_MAX_CHARGE_POWER,
            ),
            CONF_SOLAR_BALANCE_PHASES: (
                self._solar_balance_phases,
                DEFAULT_SOLAR_BALANCE_PHASES,
            ),
            CONF_SOLAR_BALANCE_START_DELAY: (
                self._solar_balance_start_delay,
                DEFAULT_SOLAR_BALANCE_START_DELAY,
            ),
            CONF_SOLAR_BALANCE_USE_BATTERY_CHARGE: (
                self._solar_balance_use_battery_charge,
                DEFAULT_SOLAR_BALANCE_USE_BATTERY_CHARGE,
            ),
            CONF_SOLAR_BALANCE_SOC_MID: (
                self._solar_balance_soc_mid,
                DEFAULT_SOLAR_BALANCE_SOC_MID,
            ),
            CONF_SOLAR_BALANCE_SOC_HIGH: (
                self._solar_balance_soc_high,
                DEFAULT_SOLAR_BALANCE_SOC_HIGH,
            ),
            CONF_SOLAR_BALANCE_MID_RESERVE_POWER: (
                self._solar_balance_mid_reserve_power,
                DEFAULT_SOLAR_BALANCE_MID_RESERVE_POWER,
            ),
            CONF_SOLAR_BALANCE_HIGH_RESERVE_POWER: (
                self._solar_balance_high_reserve_power,
                DEFAULT_SOLAR_BALANCE_HIGH_RESERVE_POWER,
            ),
            CONF_SOLAR_BALANCE_TARGET_EXPORT_POWER: (
                self._solar_balance_target_export_power,
                DEFAULT_SOLAR_BALANCE_TARGET_EXPORT_POWER,
            ),
            CONF_SOLAR_BALANCE_DEADBAND_POWER: (
                self._solar_balance_deadband_power,
                DEFAULT_SOLAR_BALANCE_DEADBAND_POWER,
            ),
            CONF_SOLAR_BALANCE_INCREASE_INTERVAL: (
                self._solar_balance_increase_interval,
                DEFAULT_SOLAR_BALANCE_INCREASE_INTERVAL,
            ),
            CONF_SOLAR_BALANCE_INCREASE_STEP: (
                self._solar_balance_increase_step,
                DEFAULT_SOLAR_BALANCE_INCREASE_STEP,
            ),
            CONF_SOLAR_BALANCE_DECREASE_STEP: (
                self._solar_balance_decrease_step,
                DEFAULT_SOLAR_BALANCE_DECREASE_STEP,
            ),
            CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER: (
                self._solar_balance_residual_export_power,
                DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER,
            ),
            CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY: (
                self._solar_balance_residual_export_delay,
                DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY,
            ),
            CONF_SOLAR_BALANCE_DRY_RUN: (
                self._solar_balance_dry_run,
                DEFAULT_SOLAR_BALANCE_DRY_RUN,
            ),
        }
        config_data.update(
            {
                key: value
                for key, (value, default) in optional_data.items()
                if value != default
            }
        )
        return self.async_create_entry(
            title="Silla Prism",
            data=config_data,
        )

    async def _async_update_entry(self) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()

        config_data = {
            CONF_TOPIC: self._topic,
            CONF_PORTS: entry.data.get(CONF_PORTS, DEFAULT_PORTS),
            CONF_SERIAL: entry.data.get(CONF_SERIAL, DEFAULT_SERIAL),
            CONF_VSENSORS: entry.data.get(CONF_VSENSORS, DEFAULT_VSENSORS),
            CONF_POWERWALL: entry.data.get(CONF_POWERWALL, DEFAULT_POWERWALL),
            CONF_MAX_CURRENT: self._max_current,
            CONF_SOLAR_BATTERY_BALANCE: self._solar_battery_balance,
            CONF_BATTERY_POWER_SENSOR: self._battery_power_sensor,
            CONF_SOLAR_PRODUCTION_POWER_SENSOR: self._solar_production_power_sensor,
            CONF_HOME_LOAD_POWER_SENSOR: self._home_load_power_sensor,
            CONF_HOME_LOAD_INCLUDES_EV: self._home_load_includes_ev,
            CONF_BATTERY_SOC_SENSOR: self._battery_soc_sensor,
            CONF_BATTERY_DISCHARGE_POSITIVE: self._battery_discharge_positive,
            CONF_BATTERY_MAX_CHARGE_POWER: self._battery_max_charge_power,
            CONF_SOLAR_BALANCE_PHASES: self._solar_balance_phases,
            CONF_SOLAR_BALANCE_START_DELAY: self._solar_balance_start_delay,
            CONF_SOLAR_BALANCE_USE_BATTERY_CHARGE: (
                self._solar_balance_use_battery_charge
            ),
            CONF_SOLAR_BALANCE_SOC_MID: self._solar_balance_soc_mid,
            CONF_SOLAR_BALANCE_SOC_HIGH: self._solar_balance_soc_high,
            CONF_SOLAR_BALANCE_MID_RESERVE_POWER: (
                self._solar_balance_mid_reserve_power
            ),
            CONF_SOLAR_BALANCE_HIGH_RESERVE_POWER: (
                self._solar_balance_high_reserve_power
            ),
            CONF_SOLAR_BALANCE_TARGET_EXPORT_POWER: (
                self._solar_balance_target_export_power
            ),
            CONF_SOLAR_BALANCE_DEADBAND_POWER: self._solar_balance_deadband_power,
            CONF_SOLAR_BALANCE_INCREASE_INTERVAL: (
                self._solar_balance_increase_interval
            ),
            CONF_SOLAR_BALANCE_INCREASE_STEP: self._solar_balance_increase_step,
            CONF_SOLAR_BALANCE_DECREASE_STEP: self._solar_balance_decrease_step,
            CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER: (
                self._solar_balance_residual_export_power
            ),
            CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY: (
                self._solar_balance_residual_export_delay
            ),
            CONF_SOLAR_BALANCE_DRY_RUN: self._solar_balance_dry_run,
        }
        return self.async_update_reload_and_abort(
            self._get_reconfigure_entry(),
            data_updates=config_data,
        )

    @override
    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via the Prism hello topic."""
        payload = discovery_info.payload
        if not payload or not isinstance(payload, str):
            return self.async_abort(reason="invalid_discovery_info")

        self._topic = discovery_info.topic.removesuffix("/hello")
        if self._topic == discovery_info.topic:
            return self.async_abort(reason="invalid_discovery_info")

        try:
            discovered_serial = parse_hello(payload).serial
        except PrismParseError:
            return self.async_abort(reason="invalid_discovery_info")

        await self.async_set_unique_id(self._topic)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"serial": discovered_serial}
        self._discovered_serial = discovered_serial
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered Prism."""
        if user_input is not None:
            return await self._async_create_entry()

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"serial": self._discovered_serial},
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _LOGGER.info("Async_step_user %s", DOMAIN)
        return await self._async_step_user_base(user_input=user_input)
