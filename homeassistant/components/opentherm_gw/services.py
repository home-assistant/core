"""OpenTherm Gateway service actions."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
import logging
from typing import TYPE_CHECKING

from pyotgw import vars as gw_vars
import voluptuous as vol

from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DATE,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_ID,
    ATTR_MODE,
    ATTR_TEMPERATURE,
    ATTR_TIME,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

if TYPE_CHECKING:
    from . import OpenThermGatewayHub

from .const import (
    ATTR_CH_OVRD,
    ATTR_DHW_OVRD,
    ATTR_GW_ID,
    ATTR_LEVEL,
    ATTR_TRANSP_ARG,
    ATTR_TRANSP_CMD,
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

ATTR_DATETIME = "datetime"

SERVICE_REBOOT_GATEWAY = "reboot_gateway"
SERVICE_RESET_GATEWAY = "reset_gateway"
SERVICE_SET_CH_OVRD = "set_central_heating_ovrd"
SERVICE_SET_CLOCK = "set_clock"
SERVICE_SET_CONTROL_SETPOINT = "set_control_setpoint"
SERVICE_SET_HOT_WATER_SETPOINT = "set_hot_water_setpoint"
SERVICE_SET_HOT_WATER_OVRD = "set_hot_water_ovrd"
SERVICE_SET_GPIO_MODE = "set_gpio_mode"
SERVICE_SET_LED_MODE = "set_led_mode"
SERVICE_SET_MAX_MOD = "set_max_modulation"
SERVICE_SET_OAT = "set_outside_temperature"
SERVICE_SET_SB_TEMP = "set_setback_temperature"
SERVICE_SEND_TRANSP_CMD = "send_transparent_command"


@callback
def async_get_hub_from_device_id(
    hass: HomeAssistant, device_id: str, dev_reg: dr.DeviceRegistry | None = None
) -> OpenThermGatewayHub:
    """Return an OpenThermGatewayHub from a device id."""
    dev_reg = dr.async_get(hass) if dev_reg is None else dev_reg

    if not (device_entry := dev_reg.async_get(device_id)):
        raise ValueError(f"Device ID {device_id} is not valid")

    config_entry_ids = device_entry.config_entries
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        if config_entry.entry_id in config_entry_ids:
            return hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][
                config_entry.data[ATTR_ID]
            ]

    raise ValueError(f"No {DOMAIN} config entry found for device ID {device_id}")


@callback
def async_get_hub_from_entity_id(
    hass: HomeAssistant, entity_id: str, ent_reg: er.EntityRegistry | None = None
) -> OpenThermGatewayHub:
    """Return an OpenThermGatewayHub from an entity id."""
    ent_reg = er.async_get(hass) if ent_reg is None else ent_reg

    if not (entity_entry := ent_reg.async_get(entity_id)):
        raise ValueError(f"Entity ID {entity_id} is not valid")

    for config_entry in hass.config_entries.async_entries(DOMAIN):
        if config_entry.entry_id == entity_entry.config_entry_id:
            return hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][
                config_entry.data[ATTR_ID]
            ]

    raise ValueError(f"No {DOMAIN} config entry found for entity ID {entity_id}")


@callback
def async_get_hubs_from_area_id(
    hass: HomeAssistant,
    area_id: str,
    dev_reg: dr.DeviceRegistry | None = None,
    ent_reg: er.EntityRegistry | None = None,
) -> set[OpenThermGatewayHub]:
    """Return all OpenThermGatewayHubs that have a device or entity in an area."""
    dev_reg = dr.async_get(hass) if dev_reg is None else dev_reg
    ent_reg = er.async_get(hass) if ent_reg is None else ent_reg

    hubs: set[OpenThermGatewayHub] = set()

    for device in dr.async_entries_for_area(dev_reg, area_id):
        for config_entry_id in device.config_entries:
            if (
                config_entry := hass.config_entries.async_get_entry(config_entry_id)
            ) is None:
                continue
            if config_entry.domain == DOMAIN:
                hubs.add(
                    hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][
                        config_entry.data[ATTR_ID]
                    ]
                )

    for entity in er.async_entries_for_area(ent_reg, area_id):
        if entity.config_entry_id is None:
            continue
        if (
            config_entry := hass.config_entries.async_get_entry(entity.config_entry_id)
        ) is None:
            continue
        if config_entry.domain == DOMAIN:
            hubs.add(
                hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[ATTR_ID]]
            )

    return hubs


@callback
def async_get_hubs_from_service_data(
    hass: HomeAssistant, service_data: dict
) -> set[OpenThermGatewayHub]:
    """Return OpenThermGatewayHubs from the information in service_data."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    hubs: set[OpenThermGatewayHub] = set()

    # ATTR_GW_ID support is deprecated.
    # This should be removed in 2025.1.0
    if gw_id := service_data.get(ATTR_GW_ID):
        ir.async_create_issue(
            hass,
            DOMAIN,
            "gw_id_in_service_call",
            breaks_in_ha_version="2025.1.0",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            learn_more_url="https://www.home-assistant.io/integrations/opentherm_gw/#actions",
            translation_key="gw_id_in_service_call",
        )
        _LOGGER.warning(
            "The use of the 'gateway_id' parameter in opentherm_gw actions has been deprecated "
            "in favor of the 'target' parameter. This will stop working in Home Assistant "
            "2025.1.0. Please update your configuration accordingly"
        )
        hubs.add(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][gw_id])

    for area_id in service_data.get(ATTR_AREA_ID, []):
        hubs.update(async_get_hubs_from_area_id(hass, area_id, dev_reg, ent_reg))

    for device_id in service_data.get(ATTR_DEVICE_ID, []):
        hubs.add(async_get_hub_from_device_id(hass, device_id, dev_reg))

    for entity_id in service_data.get(ATTR_ENTITY_ID, []):
        hubs.add(async_get_hub_from_entity_id(hass, entity_id, ent_reg))

    return hubs


def register_services(hass: HomeAssistant) -> None:
    """Register services for the component."""

    opentherm_base_service_schema = vol.Schema(
        vol.All(
            {
                # ATTR_GW_ID support is deprecated.
                # This should be removed in 2025.1.0
                vol.Optional(ATTR_GW_ID): vol.All(
                    cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
                ),
                vol.Optional(ATTR_AREA_ID): vol.All(cv.ensure_list, [cv.string]),
                vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
                vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
            },
            cv.has_at_least_one_key(
                ATTR_GW_ID, ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID
            ),
        )
    )

    async def reboot_gateway(call: ServiceCall) -> None:
        """Reboot the OpenTherm Gateway."""
        gw_hubs = async_get_hubs_from_service_data(hass, call.data)
        mode_rst = gw_vars.OTGW_MODE_RESET
        await asyncio.gather(*(gw_hub.gateway.set_mode(mode_rst) for gw_hub in gw_hubs))

    hass.services.async_register(
        DOMAIN,
        SERVICE_REBOOT_GATEWAY,
        reboot_gateway,
        opentherm_base_service_schema,
    )

    async def reset_gateway(call: ServiceCall) -> None:
        """Reset the OpenTherm Gateway."""
        ir.async_create_issue(
            hass,
            DOMAIN,
            "reset_gateway_renamed_to_reboot_gateway",
            breaks_in_ha_version="2025.1.0",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            learn_more_url="https://www.home-assistant.io/integrations/opentherm_gw/#action-opentherm_gwreboot_gateway",
            translation_key="reset_gateway_renamed_to_reboot_gateway",
        )
        _LOGGER.warning(
            "Action 'opentherm_gw.reset_gateway' has been renamed to 'opentherm_gw.reboot_gateway'. This will stop "
            "working in Home Assistant 2025.1.0. Please update your configuration accordingly"
        )
        await reboot_gateway(call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_GATEWAY,
        reset_gateway,
        opentherm_base_service_schema,
    )

    async def set_ch_ovrd(call: ServiceCall) -> None:
        """Set the central heating override on the OpenTherm Gateway."""
        gw_hubs = async_get_hubs_from_service_data(hass, call.data)
        await asyncio.gather(
            *(
                gw_hub.gateway.set_ch_enable_bit(1 if call.data[ATTR_CH_OVRD] else 0)
                for gw_hub in gw_hubs
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CH_OVRD,
        set_ch_ovrd,
        opentherm_base_service_schema.extend(
            {
                vol.Required(ATTR_CH_OVRD): cv.boolean,
            },
        ),
    )

    async def set_clock(call: ServiceCall) -> None:
        """Set the clock on the OpenTherm Gateway."""
        dt_param = call.data.get(ATTR_DATETIME)

        # ATTR_DATE and ATTR_TIME support is deprecated
        # This should be removed in 2025.1.0
        if ATTR_DATE in call.data:
            ir.async_create_issue(
                hass,
                DOMAIN,
                "attr_date_or_attr_time_in_set_clock_service_call",
                breaks_in_ha_version="2025.1.0",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                learn_more_url="https://www.home-assistant.io/integrations/opentherm_gw/#action-opentherm_gwset_clock",
                translation_key="attr_date_or_attr_time_in_set_clock_service_call",
            )
            _LOGGER.warning(
                "The use of 'date' and/or 'time' parameters in action 'opentherm_gw.set_clock has been deprecated in "
                "favor of the combined 'datetime' parameter. This will stop working in Home Assistant 2025.1.0. "
                "Please update your configuration accordingly"
            )
            dt_param = datetime.combine(call.data[ATTR_DATE], call.data[ATTR_TIME])

        gw_hubs = async_get_hubs_from_service_data(hass, call.data)
        await asyncio.gather(
            *(gw_hub.gateway.set_clock(dt_param) for gw_hub in gw_hubs)
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CLOCK,
        set_clock,
        vol.Schema(
            vol.Any(
                opentherm_base_service_schema.extend(
                    {
                        vol.Optional(ATTR_DATETIME, default=datetime.now): cv.datetime,
                    },
                ),
                # ATTR_DATE and ATTR_TIME support is deprecated
                # This should be removed in 2025.1.0
                opentherm_base_service_schema.extend(
                    {
                        vol.Optional(ATTR_DATE, default=date.today): cv.date,
                        vol.Optional(
                            ATTR_TIME, default=lambda: datetime.now().time()
                        ): cv.time,
                    },
                ),
            ),
        ),
    )

    async def set_control_setpoint(call: ServiceCall) -> None:
        """Set the control setpoint on the OpenTherm Gateway."""
        gw_hubs = async_get_hubs_from_service_data(hass, call.data)
        await asyncio.gather(
            *(
                gw_hub.gateway.set_control_setpoint(call.data[ATTR_TEMPERATURE])
                for gw_hub in gw_hubs
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CONTROL_SETPOINT,
        set_control_setpoint,
        opentherm_base_service_schema.extend(
            {
                vol.Required(ATTR_TEMPERATURE): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=90)
                ),
            },
        ),
    )

    async def set_dhw_setpoint(call: ServiceCall) -> None:
        """Set the domestic hot water setpoint on the OpenTherm Gateway."""
        gw_hubs = async_get_hubs_from_service_data(hass, call.data)
        await asyncio.gather(
            *(
                gw_hub.gateway.set_dhw_setpoint(call.data[ATTR_TEMPERATURE])
                for gw_hub in gw_hubs
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOT_WATER_SETPOINT,
        set_dhw_setpoint,
        opentherm_base_service_schema.extend(
            {
                vol.Required(ATTR_TEMPERATURE): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=90)
                ),
            },
        ),
    )

    async def set_dhw_ovrd(call: ServiceCall) -> None:
        """Set the domestic hot water override on the OpenTherm Gateway."""
        gw_hubs = async_get_hubs_from_service_data(hass, call.data)
        await asyncio.gather(
            *(
                gw_hub.gateway.set_hot_water_ovrd(call.data[ATTR_DHW_OVRD])
                for gw_hub in gw_hubs
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOT_WATER_OVRD,
        set_dhw_ovrd,
        opentherm_base_service_schema.extend(
            {
                vol.Required(ATTR_DHW_OVRD): vol.Any(
                    vol.Equal("A"), vol.All(vol.Coerce(int), vol.Range(min=0, max=1))
                ),
            },
        ),
    )

    async def set_gpio_mode(call: ServiceCall) -> None:
        """Set the OpenTherm Gateway GPIO modes."""
        gw_hubs = async_get_hubs_from_service_data(hass, call.data)
        gpio_id = call.data[ATTR_ID]
        gpio_mode = call.data[ATTR_MODE]
        await asyncio.gather(
            *(gw_hub.gateway.set_gpio_mode(gpio_id, gpio_mode) for gw_hub in gw_hubs)
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_GPIO_MODE,
        set_gpio_mode,
        vol.Any(
            opentherm_base_service_schema.extend(
                {
                    vol.Required(ATTR_ID): vol.Equal("A"),
                    vol.Required(ATTR_MODE): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=6)
                    ),
                }
            ),
            opentherm_base_service_schema.extend(
                {
                    vol.Required(ATTR_ID): vol.Equal("B"),
                    vol.Required(ATTR_MODE): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=7)
                    ),
                }
            ),
        ),
    )

    async def set_led_mode(call: ServiceCall) -> None:
        """Set the OpenTherm Gateway LED modes."""
        gw_hubs = async_get_hubs_from_service_data(hass, call.data)
        led_id = call.data[ATTR_ID]
        led_mode = call.data[ATTR_MODE]
        await asyncio.gather(
            *(gw_hub.gateway.set_led_mode(led_id, led_mode) for gw_hub in gw_hubs)
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_LED_MODE,
        set_led_mode,
        opentherm_base_service_schema.extend(
            {
                vol.Required(ATTR_ID): vol.In("ABCDEF"),
                vol.Required(ATTR_MODE): vol.In("RXTBOFHWCEMP"),
            },
        ),
    )

    async def set_max_mod(call: ServiceCall) -> None:
        """Set the max modulation level."""
        gw_hubs = async_get_hubs_from_service_data(hass, call.data)
        level = call.data[ATTR_LEVEL]
        if level == -1:
            # Backend only clears setting on non-numeric values.
            level = "-"
        await asyncio.gather(
            *(gw_hub.gateway.set_max_relative_mod(level) for gw_hub in gw_hubs)
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MAX_MOD,
        set_max_mod,
        opentherm_base_service_schema.extend(
            {
                vol.Required(ATTR_LEVEL): vol.All(
                    vol.Coerce(int), vol.Range(min=-1, max=100)
                ),
            },
        ),
    )

    async def set_outside_temp(call: ServiceCall) -> None:
        """Provide the outside temperature to the OpenTherm Gateway."""
        gw_hubs = async_get_hubs_from_service_data(hass, call.data)
        await asyncio.gather(
            *(
                gw_hub.gateway.set_outside_temp(call.data[ATTR_TEMPERATURE])
                for gw_hub in gw_hubs
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_OAT,
        set_outside_temp,
        opentherm_base_service_schema.extend(
            {
                vol.Required(ATTR_TEMPERATURE): vol.All(
                    vol.Coerce(float), vol.Range(min=-40, max=99)
                ),
            },
        ),
    )

    async def set_setback_temp(call: ServiceCall) -> None:
        """Set the OpenTherm Gateway SetBack temperature."""
        gw_hubs = async_get_hubs_from_service_data(hass, call.data)
        await asyncio.gather(
            *(
                gw_hub.gateway.set_setback_temp(call.data[ATTR_TEMPERATURE])
                for gw_hub in gw_hubs
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SB_TEMP,
        set_setback_temp,
        opentherm_base_service_schema.extend(
            {
                vol.Required(ATTR_TEMPERATURE): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=30)
                ),
            },
        ),
    )

    async def send_transparent_cmd(call: ServiceCall) -> None:
        """Send a transparent OpenTherm Gateway command."""
        gw_hubs = async_get_hubs_from_service_data(hass, call.data)
        transp_cmd = call.data[ATTR_TRANSP_CMD]
        transp_arg = call.data[ATTR_TRANSP_ARG]
        await asyncio.gather(
            *(
                gw_hub.gateway.send_transparent_command(transp_cmd, transp_arg)
                for gw_hub in gw_hubs
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_TRANSP_CMD,
        send_transparent_cmd,
        opentherm_base_service_schema.extend(
            {
                vol.Required(ATTR_TRANSP_CMD): vol.All(
                    cv.string, vol.Length(min=2, max=2), vol.Coerce(str.upper)
                ),
                vol.Required(ATTR_TRANSP_ARG): vol.All(
                    cv.string, vol.Length(min=1, max=12)
                ),
            },
        ),
    )
