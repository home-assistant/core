"""Common data for for the withings component tests."""
import time

import nokia

import homeassistant.components.withings.const as const


def new_sleep_data(model, series):
    """Create simple dict to simulate api data."""
    return {"series": series, "model": model}


def new_sleep_data_serie(startdate, enddate, state):
    """Create simple dict to simulate api data."""
    return {"startdate": startdate, "enddate": enddate, "state": state}


def new_sleep_summary(timezone, model, startdate, enddate, date, modified, data):
    """Create simple dict to simulate api data."""
    return {
        "timezone": timezone,
        "model": model,
        "startdate": startdate,
        "enddate": enddate,
        "date": date,
        "modified": modified,
        "data": data,
    }


def new_sleep_summary_detail(
    wakeupduration,
    lightsleepduration,
    deepsleepduration,
    remsleepduration,
    wakeupcount,
    durationtosleep,
    durationtowakeup,
    hr_average,
    hr_min,
    hr_max,
    rr_average,
    rr_min,
    rr_max,
):
    """Create simple dict to simulate api data."""
    return {
        "wakeupduration": wakeupduration,
        "lightsleepduration": lightsleepduration,
        "deepsleepduration": deepsleepduration,
        "remsleepduration": remsleepduration,
        "wakeupcount": wakeupcount,
        "durationtosleep": durationtosleep,
        "durationtowakeup": durationtowakeup,
        "hr_average": hr_average,
        "hr_min": hr_min,
        "hr_max": hr_max,
        "rr_average": rr_average,
        "rr_min": rr_min,
        "rr_max": rr_max,
    }


def new_measure_group(
    grpid, attrib, date, created, category, deviceid, more, offset, measures
):
    """Create simple dict to simulate api data."""
    return {
        "grpid": grpid,
        "attrib": attrib,
        "date": date,
        "created": created,
        "category": category,
        "deviceid": deviceid,
        "measures": measures,
        "more": more,
        "offset": offset,
        "comment": "blah",  # deprecated
    }


def new_measure(type_str, value, unit):
    """Create simple dict to simulate api data."""
    return {
        "value": value,
        "type": type_str,
        "unit": unit,
        "algo": -1,  # deprecated
        "fm": -1,  # deprecated
        "fw": -1,  # deprecated
    }


def nokia_sleep_response(states):
    """Create a sleep response based on states."""
    data = []
    for state in states:
        data.append(
            new_sleep_data_serie(
                "2019-02-01 0{}:00:00".format(str(len(data))),
                "2019-02-01 0{}:00:00".format(str(len(data) + 1)),
                state,
            )
        )

    return nokia.NokiaSleep(new_sleep_data("aa", data))


NOKIA_MEASURES_RESPONSE = nokia.NokiaMeasures(
    {
        "updatetime": "",
        "timezone": "",
        "measuregrps": [
            # Un-ambiguous groups.
            new_measure_group(
                1,
                0,
                time.time(),
                time.time(),
                1,
                "DEV_ID",
                False,
                0,
                [
                    new_measure(const.MEASURE_TYPE_WEIGHT, 70, 0),
                    new_measure(const.MEASURE_TYPE_FAT_MASS, 5, 0),
                    new_measure(const.MEASURE_TYPE_FAT_MASS_FREE, 60, 0),
                    new_measure(const.MEASURE_TYPE_MUSCLE_MASS, 50, 0),
                    new_measure(const.MEASURE_TYPE_BONE_MASS, 10, 0),
                    new_measure(const.MEASURE_TYPE_HEIGHT, 2, 0),
                    new_measure(const.MEASURE_TYPE_TEMP, 40, 0),
                    new_measure(const.MEASURE_TYPE_BODY_TEMP, 35, 0),
                    new_measure(const.MEASURE_TYPE_SKIN_TEMP, 20, 0),
                    new_measure(const.MEASURE_TYPE_FAT_RATIO, 70, -3),
                    new_measure(const.MEASURE_TYPE_DIASTOLIC_BP, 70, 0),
                    new_measure(const.MEASURE_TYPE_SYSTOLIC_BP, 100, 0),
                    new_measure(const.MEASURE_TYPE_HEART_PULSE, 60, 0),
                    new_measure(const.MEASURE_TYPE_SPO2, 95, -2),
                    new_measure(const.MEASURE_TYPE_HYDRATION, 95, -2),
                    new_measure(const.MEASURE_TYPE_PWV, 100, 0),
                ],
            ),
            # Ambiguous groups (we ignore these)
            new_measure_group(
                1,
                1,
                time.time(),
                time.time(),
                1,
                "DEV_ID",
                False,
                0,
                [
                    new_measure(const.MEASURE_TYPE_WEIGHT, 71, 0),
                    new_measure(const.MEASURE_TYPE_FAT_MASS, 4, 0),
                    new_measure(const.MEASURE_TYPE_MUSCLE_MASS, 51, 0),
                    new_measure(const.MEASURE_TYPE_BONE_MASS, 11, 0),
                    new_measure(const.MEASURE_TYPE_HEIGHT, 201, 0),
                    new_measure(const.MEASURE_TYPE_TEMP, 41, 0),
                    new_measure(const.MEASURE_TYPE_BODY_TEMP, 34, 0),
                    new_measure(const.MEASURE_TYPE_SKIN_TEMP, 21, 0),
                    new_measure(const.MEASURE_TYPE_FAT_RATIO, 71, -3),
                    new_measure(const.MEASURE_TYPE_DIASTOLIC_BP, 71, 0),
                    new_measure(const.MEASURE_TYPE_SYSTOLIC_BP, 101, 0),
                    new_measure(const.MEASURE_TYPE_HEART_PULSE, 61, 0),
                    new_measure(const.MEASURE_TYPE_SPO2, 98, -2),
                    new_measure(const.MEASURE_TYPE_HYDRATION, 96, -2),
                    new_measure(const.MEASURE_TYPE_PWV, 102, 0),
                ],
            ),
        ],
    }
)


NOKIA_SLEEP_RESPONSE = nokia_sleep_response(
    [
        const.MEASURE_TYPE_SLEEP_STATE_AWAKE,
        const.MEASURE_TYPE_SLEEP_STATE_LIGHT,
        const.MEASURE_TYPE_SLEEP_STATE_REM,
        const.MEASURE_TYPE_SLEEP_STATE_DEEP,
    ]
)

NOKIA_SLEEP_SUMMARY_RESPONSE = nokia.NokiaSleepSummary(
    {
        "series": [
            new_sleep_summary(
                "UTC",
                32,
                "2019-02-01",
                "2019-02-02",
                "2019-02-02",
                "12345",
                new_sleep_summary_detail(
                    110, 210, 310, 410, 510, 610, 710, 810, 910, 1010, 1110, 1210, 1310
                ),
            ),
            new_sleep_summary(
                "UTC",
                32,
                "2019-02-01",
                "2019-02-02",
                "2019-02-02",
                "12345",
                new_sleep_summary_detail(
                    210, 310, 410, 510, 610, 710, 810, 910, 1010, 1110, 1210, 1310, 1410
                ),
            ),
        ]
    }
)
