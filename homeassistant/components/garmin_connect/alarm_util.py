"""Utility method for converting Garmin Connect alarms to python datetime."""
from datetime import date, datetime, timedelta
import logging

_LOGGER = logging.getLogger(__name__)

DAY_TO_NUMBER = {
    "Mo": 1,
    "M": 1,
    "Tu": 2,
    "We": 3,
    "W": 3,
    "Th": 4,
    "Fr": 5,
    "F": 5,
    "Sa": 6,
    "Su": 7,
}


def calculate_next_active_alarms(alarms):
    """
    Calculate garmin next active alarms from settings.

    Alarms are sorted by time
    """
    active_alarms = []
    _LOGGER.debug(alarms)

    for alarm_setting in alarms:
        if alarm_setting["alarmMode"] != "ON":
            continue
        for day in alarm_setting["alarmDays"]:
            alarm_time = alarm_setting["alarmTime"]
            if day == "ONCE":
                midnight = datetime.combine(date.today(), datetime.min.time())
                alarm = midnight + timedelta(minutes=alarm_time)
                if alarm < datetime.now():
                    alarm += timedelta(days=1)
            else:
                start_of_week = datetime.combine(
                    date.today() - timedelta(days=datetime.today().isoweekday() % 7),
                    datetime.min.time(),
                )
                days_to_add = DAY_TO_NUMBER[day] % 7
                alarm = start_of_week + timedelta(minutes=alarm_time, days=days_to_add)
                if alarm < datetime.now():
                    alarm += timedelta(days=7)
            active_alarms.append(alarm.isoformat())
    return sorted(active_alarms) if active_alarms else None
