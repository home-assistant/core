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
            if day == "ONCE":
                midnight = datetime.combine(date.today(), datetime.min.time())
                alarmtime = alarm_setting["alarmTime"]
                alarm = midnight + timedelta(minutes=alarmtime)
                if alarm < datetime.now():
                    alarm += timedelta(days=1)
                active_alarms.append(alarm.isoformat())
            else:
                start_of_week = datetime.combine(
                    date.today() - timedelta(days=datetime.today().isoweekday() % 7),
                    datetime.min.time(),
                )
                alarmtime = alarm_setting["alarmTime"]
                days_to_add = DAY_TO_NUMBER[day] % 7
                alarm = start_of_week + timedelta(minutes=alarmtime, days=days_to_add)
                if alarm < datetime.now():
                    alarm += timedelta(days=7)
                active_alarms.append(alarm.isoformat())
    return sorted(active_alarms) if len(active_alarms) > 0 else None
