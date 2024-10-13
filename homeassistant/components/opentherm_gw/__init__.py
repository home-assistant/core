"""Support for OpenTherm Gateway devices."""

import asyncio
from datetime import date, datetime
import logging

from pyotgw import OpenThermGateway
import pyotgw.vars as gw_vars
from serial import SerialException
import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_DATE,
    ATTR_ID,
    ATTR_MODE,
    ATTR_TEMPERATURE,
    ATTR_TIME,
    CONF_DEVICE,
    CONF_ID,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CH_OVRD,
    ATTR_DHW_OVRD,
    ATTR_GW_ID,
    ATTR_LEVEL,
    ATTR_TRANSP_ARG,
    ATTR_TRANSP_CMD,
    CONF_CLIMATE,
    CONF_FLOOR_TEMP,
    CONF_PRECISION,
    CONNECTION_TIMEOUT,
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
    DOMAIN,
    SERVICE_RESET_GATEWAY,
    SERVICE_SEND_TRANSP_CMD,
    SERVICE_SET_CH_OVRD,
    SERVICE_SET_CLOCK,
    SERVICE_SET_CONTROL_SETPOINT,
    SERVICE_SET_GPIO_MODE,
    SERVICE_SET_HOT_WATER_OVRD,
    SERVICE_SET_HOT_WATER_SETPOINT,
    SERVICE_SET_LED_MODE,
    SERVICE_SET_MAX_MOD,
    SERVICE_SET_OAT,
    SERVICE_SET_SB_TEMP,
    OpenThermDataSource,
    OpenThermDeviceIdentifier,
)

_LOGGER = logging.getLogger(__name__)

# *_SCHEMA required for deprecated import from configuration.yaml, can be removed in 2025.4.0
CLIMATE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
        vol.Optional(CONF_FLOOR_TEMP, default=False): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            {
                vol.Required(CONF_DEVICE): cv.string,
                vol.Optional(CONF_CLIMATE, default={}): CLIMATE_SCHEMA,
                vol.Optional(CONF_NAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    gateway = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][entry.data[CONF_ID]]
    async_dispatcher_send(hass, gateway.options_update_signal, entry)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the OpenTherm Gateway component."""
    if DATA_OPENTHERM_GW not in hass.data:
        hass.data[DATA_OPENTHERM_GW] = {DATA_GATEWAYS: {}}

    gateway = OpenThermGatewayHub(hass, config_entry)
    hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]] = gateway

    # Migration can be removed in 2025.4.0
    dev_reg = dr.async_get(hass)
    if (
        migrate_device := dev_reg.async_get_device(
            {(DOMAIN, config_entry.data[CONF_ID])}
        )
    ) is not None:
        dev_reg.async_update_device(
            migrate_device.id,
            new_identifiers={
                (
                    DOMAIN,
                    f"{config_entry.data[CONF_ID]}-{OpenThermDeviceIdentifier.GATEWAY}",
                )
            },
        )

    # Migration can be removed in 2025.4.0
    ent_reg = er.async_get(hass)
    if (
        entity_id := ent_reg.async_get_entity_id(
            CLIMATE_DOMAIN, DOMAIN, config_entry.data[CONF_ID]
        )
    ) is not None:
        ent_reg.async_update_entity(
            entity_id,
            new_unique_id=f"{config_entry.data[CONF_ID]}-{OpenThermDeviceIdentifier.THERMOSTAT}-thermostat_entity",
        )

    config_entry.add_update_listener(options_updated)

    try:
        async with asyncio.timeout(CONNECTION_TIMEOUT):
            await gateway.connect_and_subscribe()
    except (TimeoutError, ConnectionError, SerialException) as ex:
        await gateway.cleanup()
        raise ConfigEntryNotReady(
            f"Could not connect to gateway at {gateway.device_path}: {ex}"
        ) from ex

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    register_services(hass)
    return True


# Deprecated import from configuration.yaml, can be removed in 2025.4.0
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OpenTherm Gateway component."""
    if DOMAIN in config:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "deprecated_import_from_configuration_yaml",
            breaks_in_ha_version="2025.4.0",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_import_from_configuration_yaml",
        )
    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        conf = config[DOMAIN]
        for device_id, device_config in conf.items():
            device_config[CONF_ID] = device_id

            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=device_config
                )
            )
    return True


def register_services(hass: HomeAssistant) -> None:
    """Register services for the component."""
    service_reset_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            )
        }
    )
    service_set_central_heating_ovrd_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Required(ATTR_CH_OVRD): cv.boolean,
        }
    )
    service_set_clock_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Optional(ATTR_DATE, default=date.today): cv.date,
            vol.Optional(ATTR_TIME, default=lambda: datetime.now().time()): cv.time,
        }
    )
    service_set_control_setpoint_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Required(ATTR_TEMPERATURE): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=90)
            ),
        }
    )
    service_set_hot_water_setpoint_schema = service_set_control_setpoint_schema
    service_set_hot_water_ovrd_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Required(ATTR_DHW_OVRD): vol.Any(
                vol.Equal("A"), vol.All(vol.Coerce(int), vol.Range(min=0, max=1))
            ),
        }
    )
    service_set_gpio_mode_schema = vol.Schema(
        vol.Any(
            vol.Schema(
                {
                    vol.Required(ATTR_GW_ID): vol.All(
                        cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
                    ),
                    vol.Required(ATTR_ID): vol.Equal("A"),
                    vol.Required(ATTR_MODE): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=6)
                    ),
                }
            ),
            vol.Schema(
                {
                    vol.Required(ATTR_GW_ID): vol.All(
                        cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
                    ),
                    vol.Required(ATTR_ID): vol.Equal("B"),
                    vol.Required(ATTR_MODE): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=7)
                    ),
                }
            ),
        )
    )
    service_set_led_mode_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Required(ATTR_ID): vol.In("ABCDEF"),
            vol.Required(ATTR_MODE): vol.In("RXTBOFHWCEMP"),
        }
    )
    service_set_max_mod_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Required(ATTR_LEVEL): vol.All(
                vol.Coerce(int), vol.Range(min=-1, max=100)
            ),
        }
    )
    service_set_oat_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Required(ATTR_TEMPERATURE): vol.All(
                vol.Coerce(float), vol.Range(min=-40, max=99)
            ),
        }
    )
    service_set_sb_temp_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Required(ATTR_TEMPERATURE): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=30)
            ),
        }
    )
    service_send_transp_cmd_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Required(ATTR_TRANSP_CMD): vol.All(
                cv.string, vol.Length(min=2, max=2), vol.Coerce(str.upper)
            ),
            vol.Required(ATTR_TRANSP_ARG): vol.All(
                cv.string, vol.Length(min=1, max=12)
            ),
        }
    )

    async def reset_gateway(call: ServiceCall) -> None:
        """Reset the OpenTherm Gateway."""
        gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        mode_rst = gw_vars.OTGW_MODE_RESET
        await gw_hub.gateway.set_mode(mode_rst)

    hass.services.async_register(
        DOMAIN, SERVICE_RESET_GATEWAY, reset_gateway, service_reset_schema
    )

    async def set_ch_ovrd(call: ServiceCall) -> None:
        """Set the central heating override on the OpenTherm Gateway."""
        gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        await gw_hub.gateway.set_ch_enable_bit(1 if call.data[ATTR_CH_OVRD] else 0)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CH_OVRD,
        set_ch_ovrd,
        service_set_central_heating_ovrd_schema,
    )

    async def set_control_setpoint(call: ServiceCall) -> None:
        """Set the control setpoint on the OpenTherm Gateway."""
        gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        await gw_hub.gateway.set_control_setpoint(call.data[ATTR_TEMPERATURE])

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CONTROL_SETPOINT,
        set_control_setpoint,
        service_set_control_setpoint_schema,
    )

    async def set_dhw_ovrd(call: ServiceCall) -> None:
        """Set the domestic hot water override on the OpenTherm Gateway."""
        gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        await gw_hub.gateway.set_hot_water_ovrd(call.data[ATTR_DHW_OVRD])

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOT_WATER_OVRD,
        set_dhw_ovrd,
        service_set_hot_water_ovrd_schema,
    )

    async def set_dhw_setpoint(call: ServiceCall) -> None:
        """Set the domestic hot water setpoint on the OpenTherm Gateway."""
        gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        await gw_hub.gateway.set_dhw_setpoint(call.data[ATTR_TEMPERATURE])

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOT_WATER_SETPOINT,
        set_dhw_setpoint,
        service_set_hot_water_setpoint_schema,
    )

    async def set_device_clock(call: ServiceCall) -> None:
        """Set the clock on the OpenTherm Gateway."""
        gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        attr_date = call.data[ATTR_DATE]
        attr_time = call.data[ATTR_TIME]
        await gw_hub.gateway.set_clock(datetime.combine(attr_date, attr_time))

    hass.services.async_register(
        DOMAIN, SERVICE_SET_CLOCK, set_device_clock, service_set_clock_schema
    )

    async def set_gpio_mode(call: ServiceCall) -> None:
        """Set the OpenTherm Gateway GPIO modes."""
        gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        gpio_id = call.data[ATTR_ID]
        gpio_mode = call.data[ATTR_MODE]
        await gw_hub.gateway.set_gpio_mode(gpio_id, gpio_mode)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_GPIO_MODE, set_gpio_mode, service_set_gpio_mode_schema
    )

    async def set_led_mode(call: ServiceCall) -> None:
        """Set the OpenTherm Gateway LED modes."""
        gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        led_id = call.data[ATTR_ID]
        led_mode = call.data[ATTR_MODE]
        await gw_hub.gateway.set_led_mode(led_id, led_mode)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_LED_MODE, set_led_mode, service_set_led_mode_schema
    )

    async def set_max_mod(call: ServiceCall) -> None:
        """Set the max modulation level."""
        gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        level = call.data[ATTR_LEVEL]
        if level == -1:
            # Backend only clears setting on non-numeric values.
            level = "-"
        await gw_hub.gateway.set_max_relative_mod(level)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_MAX_MOD, set_max_mod, service_set_max_mod_schema
    )

    async def set_outside_temp(call: ServiceCall) -> None:
        """Provide the outside temperature to the OpenTherm Gateway."""
        gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        await gw_hub.gateway.set_outside_temp(call.data[ATTR_TEMPERATURE])

    hass.services.async_register(
        DOMAIN, SERVICE_SET_OAT, set_outside_temp, service_set_oat_schema
    )

    async def set_setback_temp(call: ServiceCall) -> None:
        """Set the OpenTherm Gateway SetBack temperature."""
        gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        await gw_hub.gateway.set_setback_temp(call.data[ATTR_TEMPERATURE])

    hass.services.async_register(
        DOMAIN, SERVICE_SET_SB_TEMP, set_setback_temp, service_set_sb_temp_schema
    )

    async def send_transparent_cmd(call: ServiceCall) -> None:
        """Send a transparent OpenTherm Gateway command."""
        gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        transp_cmd = call.data[ATTR_TRANSP_CMD]
        transp_arg = call.data[ATTR_TRANSP_ARG]
        await gw_hub.gateway.send_transparent_command(transp_cmd, transp_arg)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_TRANSP_CMD,
        send_transparent_cmd,
        service_send_transp_cmd_schema,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Cleanup and disconnect from gateway."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    gateway = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][entry.data[CONF_ID]]
    await gateway.cleanup()
    return unload_ok


class OpenThermGatewayHub:
    """OpenTherm Gateway hub class."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the OpenTherm Gateway."""
        self.hass = hass
        self.device_path = config_entry.data[CONF_DEVICE]
        self.hub_id = config_entry.data[CONF_ID]
        self.name = config_entry.data[CONF_NAME]
        self.climate_config = config_entry.options
        self.config_entry_id = config_entry.entry_id
        self.update_signal = f"{DATA_OPENTHERM_GW}_{self.hub_id}_update"
        self.options_update_signal = f"{DATA_OPENTHERM_GW}_{self.hub_id}_options_update"
        self.gateway = OpenThermGateway()
        self.gw_version = None

    async def cleanup(self, event=None) -> None:
        """Reset overrides on the gateway."""
        await self.gateway.set_control_setpoint(0)
        await self.gateway.set_max_relative_mod("-")
        await self.gateway.disconnect()

    async def connect_and_subscribe(self) -> None:
        """Connect to serial device and subscribe report handler."""
        status = await self.gateway.connect(self.device_path)
        if not status:
            await self.cleanup()
            raise ConnectionError
        version_string = status[OpenThermDataSource.GATEWAY].get(gw_vars.OTGW_ABOUT)
        self.gw_version = version_string[18:] if version_string else None
        _LOGGER.debug(
            "Connected to OpenTherm Gateway %s at %s", self.gw_version, self.device_path
        )
        dev_reg = dr.async_get(self.hass)
        gw_dev = dev_reg.async_get_or_create(
            config_entry_id=self.config_entry_id,
            identifiers={
                (DOMAIN, f"{self.hub_id}-{OpenThermDeviceIdentifier.GATEWAY}")
            },
            manufacturer="Schelte Bron",
            model="OpenTherm Gateway",
            translation_key="gateway_device",
            sw_version=self.gw_version,
        )
        if gw_dev.sw_version != self.gw_version:
            dev_reg.async_update_device(gw_dev.id, sw_version=self.gw_version)

        boiler_device = dev_reg.async_get_or_create(
            config_entry_id=self.config_entry_id,
            identifiers={(DOMAIN, f"{self.hub_id}-{OpenThermDeviceIdentifier.BOILER}")},
            translation_key="boiler_device",
        )
        thermostat_device = dev_reg.async_get_or_create(
            config_entry_id=self.config_entry_id,
            identifiers={
                (DOMAIN, f"{self.hub_id}-{OpenThermDeviceIdentifier.THERMOSTAT}")
            },
            translation_key="thermostat_device",
        )

        self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.cleanup)

        async def handle_report(status):
            """Handle reports from the OpenTherm Gateway."""
            _LOGGER.debug("Received report: %s", status)
            async_dispatcher_send(self.hass, self.update_signal, status)

            dev_reg.async_update_device(
                boiler_device.id,
                manufacturer=status[OpenThermDataSource.BOILER].get(
                    gw_vars.DATA_SLAVE_MEMBERID
                ),
                model_id=status[OpenThermDataSource.BOILER].get(
                    gw_vars.DATA_SLAVE_PRODUCT_TYPE
                ),
                hw_version=status[OpenThermDataSource.BOILER].get(
                    gw_vars.DATA_SLAVE_PRODUCT_VERSION
                ),
                sw_version=status[OpenThermDataSource.BOILER].get(
                    gw_vars.DATA_SLAVE_OT_VERSION
                ),
            )

            dev_reg.async_update_device(
                thermostat_device.id,
                manufacturer=status[OpenThermDataSource.THERMOSTAT].get(
                    gw_vars.DATA_MASTER_MEMBERID
                ),
                model_id=status[OpenThermDataSource.THERMOSTAT].get(
                    gw_vars.DATA_MASTER_PRODUCT_TYPE
                ),
                hw_version=status[OpenThermDataSource.THERMOSTAT].get(
                    gw_vars.DATA_MASTER_PRODUCT_VERSION
                ),
                sw_version=status[OpenThermDataSource.THERMOSTAT].get(
                    gw_vars.DATA_MASTER_OT_VERSION
                ),
            )

        self.gateway.subscribe(handle_report)

    @property
    def connected(self):
        """Report whether or not we are connected to the gateway."""
        return self.gateway.connection.connected
