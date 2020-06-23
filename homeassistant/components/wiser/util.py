"""
General Utilities Wiser Platform.

https://github.com/asantaga/wiserHomeAssistantPlatform
@msp1974

"""
from datetime import datetime

from .const import SPECIALDAYS, WEEKDAYS, WEEKENDS


def convert_from_wiser_schedule(schedule_data: dict, schedule_name=""):
    """
    Convert from wiser format to human readable format.

    Param: scheduleData
    Param: mode
    """
    # Remove Id key from schedule as not needed
    if "id" in schedule_data:
        del schedule_data["id"]
    # Create dict to take converted data
    if schedule_name != "":
        schedule_output = {
            "Name": schedule_name,
            "Description": "Schedule for " + schedule_name,
            "Type": "Heating",
        }
    # Convert to human readable format for yaml
    # Iterate through each day
    for day, sched in schedule_data.items():
        if day.lower() in (WEEKDAYS + WEEKENDS + SPECIALDAYS):
            # Iterate through setpoint key for each day
            for setpoint, times in sched.items():
                if setpoint == "SetPoints":
                    # Iterate all times
                    schedule_set_points = convert_wiser_to_yaml_day(times)
                    # Iterate through each setpoint entry
            schedule_output.update({day: schedule_set_points})
    return schedule_output


def convert_to_wiser_schedule(schedule_data: dict):
    """
    Convert from human readable format to wiser format.

    Param: scheduleData
    Param: mode
    """
    # Convert to wiser format for setting schedules
    # Iterate through each day
    schedule_output = {"Type": "Heating"}
    for day, times in schedule_data.items():
        if day.lower() in (WEEKDAYS + WEEKENDS + SPECIALDAYS):
            schedule_day = {}
            # Iterate through each set of times for a day
            schedule_day = {"Setpoints": convert_yaml_to_wiser_day(times)}
            # If using special days, convert to one entry for each day of week
            if day.lower() in SPECIALDAYS:
                if day.lower() == "weekdays":
                    for weekday in WEEKDAYS:
                        schedule_output.update({weekday.capitalize(): schedule_day})
                if day.lower() == "weekends":
                    for weekend_day in WEEKENDS:
                        schedule_output.update({weekend_day.capitalize(): schedule_day})
            else:
                schedule_output.update({day: schedule_day})
    return schedule_output


def convert_wiser_to_yaml_day(times):
    """Convert from yaml to wiser schedule."""
    schedule_set_points = []
    for k in times:
        schedule_time = {}
        for key, value in k.items():
            # Convert values and keys to human readable version
            if key == "Time":
                value = (datetime.strptime(format(value, "04d"), "%H%M")).strftime(
                    "%H:%M"
                )
            if key == "DegreesC":
                key = "Temp"
                if value < 0:
                    value = "Off"
                else:
                    value = round(value / 10, 1)
            tmp = {key: value}
            schedule_time.update(tmp)
        schedule_set_points.append(schedule_time.copy())
    return schedule_set_points


def convert_yaml_to_wiser_day(times):
    """Convert from yaml to wiser schedule."""
    schedule_set_points = []
    for k in times:
        schedule_time = {}
        for key, value in k.items():
            # Convert values and key to wiser format
            if key == "Time":
                value = str(value).replace(":", "")
            if key == "Temp":
                key = "DegreesC"
                if value == "Off":
                    value = -200
                else:
                    value = int(value * 10)
            tmp = {key: value}
            schedule_time.update(tmp)
        schedule_set_points.append(schedule_time.copy())
    return schedule_set_points
