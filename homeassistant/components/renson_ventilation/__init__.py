"""Support to Renson ventilation units."""
import logging

import rensonVentilationLib.generalEnum as rensonEnums
import rensonVentilationLib.renson as renson

_LOGGER = logging.getLogger(__name__)

CONF_HOST = "host"

DOMAIN = "renson_ventilation"


def setup(hass, config):
    """Handle all the services of the Renson API."""
    host = config[DOMAIN][CONF_HOST]

    service: renson.RensonVentilation = renson.RensonVentilation(host)

    def handle_manual_level_set(call):
        level = call.data.get("manual_level", "Off").upper()
        service.set_manual_level(rensonEnums.ManualLevel[level])

    def handle_sync_time(call):
        service.sync_time()

    def handle_timer_level(call):
        level = rensonEnums.TimerLevel[call.data.get("timer_level", "Level1").upper()]
        time = call.data.get("time", 0)

        service.set_timer_level(level, time)

    def handle_set_breeze(call):
        level = rensonEnums.ManualLevel[call.data.get("breeze_level", "Off").upper()]
        temperature = call.data.get("temperature", 0)
        activated = call.data.get("activate", False)

        service.set_breeze(level, temperature, activated)

    def handle_set_time(call):
        day = call.data.get("day", "7:00")
        night = call.data.get("night", "22:00")

        service.set_time(day, night)

    def handle_set_pollution(call):
        day = call.data.get("day_pollution_level", "")
        night = call.data.get("night_pollution_level", "")
        humidity_control = call.data.get("humidity_control", "")
        airquality_control = call.data.get("airquality_control", "")
        co2_control = call.data.get("co2_control", "")
        co2_threshold = call.data.get("co2_threshold", 0)
        co2_hysteresis = call.data.get("co2_hysteresis", 0)

        service.set_pollution(
            day,
            night,
            humidity_control,
            airquality_control,
            co2_control,
            co2_threshold,
            co2_hysteresis,
        )

    def set_filter_days(call):
        days = call.data.get("days", 90)

        service.set_filter_days(days)

    hass.services.register(DOMAIN, "manual_level", handle_manual_level_set)
    hass.services.register(DOMAIN, "sync_time", handle_sync_time)
    hass.services.register(DOMAIN, "timer_level", handle_timer_level)
    hass.services.register(DOMAIN, "set_breeze", handle_set_breeze)
    hass.services.register(DOMAIN, "set_day_night_time", handle_set_time)
    hass.services.register(DOMAIN, "set_pollution_settings", handle_set_pollution)
    hass.services.register(DOMAIN, "set_filter_days", set_filter_days)

    return True
