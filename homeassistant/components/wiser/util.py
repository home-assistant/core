"""
General Utilities Wiser Platform.

https://github.com/asantaga/wiserHomeAssistantPlatform
@msp1974

"""
from datetime import datetime

from .const import SPECIALDAYS, WEEKDAYS, WEEKENDS


def convert_from_wiser_schedule(scheduleData: dict, scheduleName=""):
    """
    Convert from wiser format to human readable format.

    Param: scheduleData
    Param: mode
    """
    # Remove Id key from schedule as not needed
    if "id" in scheduleData:
        del scheduleData["id"]
    # Create dict to take converted data
    if scheduleName != "":
        scheduleOutput = {
            "Name": scheduleName,
            "Description": "Schedule for " + scheduleName,
            "Type": "Heating",
        }
    # Convert to human readable format for yaml
    # Iterate through each day
    for day, sched in scheduleData.items():
        if day.lower() in (WEEKDAYS + WEEKENDS + SPECIALDAYS):
            # Iterate through setpoint key for each day
            for setpoint, times in sched.items():
                if setpoint == "SetPoints":
                    # Iterate all times
                    schedSetpoints = []
                    # Iterate through each setpoint entry
                    for k in times:
                        schedTime = {}
                        for key, value in k.items():
                            # Convert values and keys to human readable version
                            if key == "Time":
                                value = (
                                    datetime.strptime(format(value, "04d"), "%H%M")
                                ).strftime("%H:%M")
                            if key == "DegreesC":
                                key = "Temp"
                                if value < 0:
                                    value = "Off"
                                else:
                                    value = round(value / 10, 1)
                            tmp = {key: value}
                            schedTime.update(tmp)
                        schedSetpoints.append(schedTime.copy())
            scheduleOutput.update({day: schedSetpoints})
    return scheduleOutput


def convert_to_wiser_schedule(scheduleData: dict):
    """
    Convert from human readable format to wiser format.

    Param: scheduleData
    Param: mode
    """
    # Convert to wiser format for setting schedules
    # Iterate through each day
    scheduleOutput = {"Type": "Heating"}
    for day, times in scheduleData.items():
        if day.lower() in (WEEKDAYS + WEEKENDS + SPECIALDAYS):
            schedDay = {}
            schedSetpoints = []
            # Iterate through each set of times for a day
            for k in times:
                schedTime = {}
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
                    schedTime.update(tmp)
                schedSetpoints.append(schedTime.copy())
                schedDay = {"Setpoints": schedSetpoints}
            # If using special days, convert to one entry for each day of week
            if day.lower() in SPECIALDAYS:
                if day.lower() == "weekdays":
                    for d in WEEKDAYS:
                        scheduleOutput.update({d.capitalize(): schedDay})
                if day.lower() == "weekends":
                    for d in WEEKENDS:
                        scheduleOutput.update({d.capitalize(): schedDay})
            else:
                scheduleOutput.update({day: schedDay})
    return scheduleOutput
