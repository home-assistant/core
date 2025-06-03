"""Test data for the tests of the Huisbaasje integration."""

MOCK_CURRENT_MEASUREMENTS = {
    "electricity": {
        "measurement": {
            "time": "2020-11-18T15:17:24.000Z",
            "rate": 1011.6666666666667,
            "value": 0.0033333333333333335,
            "costPerHour": 0.20233333333333337,
            "counterValue": 409.17166666631937,
        },
        "thisDay": {"value": 3.296665869, "cost": 0.6593331738},
        "thisWeek": {"value": 17.509996085, "cost": 3.5019992170000003},
        "thisMonth": {"value": 103.28830788, "cost": 20.657661576000002},
        "thisYear": {"value": 672.9781177300001, "cost": 134.595623546},
    },
    "electricityIn": {
        "measurement": {
            "time": "2020-11-18T15:17:24.000Z",
            "rate": 1011.6666666666667,
            "value": 0.0033333333333333335,
            "costPerHour": 0.20233333333333337,
            "counterValue": 409.17166666631937,
        },
        "thisDay": {"value": 2.669999453, "cost": 0.5339998906},
        "thisWeek": {"value": 15.328330291, "cost": 3.0656660582},
        "thisMonth": {"value": 72.986651896, "cost": 14.5973303792},
        "thisYear": {"value": 409.214880212, "cost": 81.84297604240001},
    },
    "electricityInLow": {
        "measurement": None,
        "thisDay": {"value": 0.6266664160000001, "cost": 0.1253332832},
        "thisWeek": {"value": 2.181665794, "cost": 0.43633315880000006},
        "thisMonth": {"value": 30.301655984000003, "cost": 6.060331196800001},
        "thisYear": {"value": 263.76323751800004, "cost": 52.75264750360001},
    },
    "electricityOut": {
        "measurement": None,
        "thisDay": {"value": 1.51234, "cost": 0.0},
        "thisWeek": {"value": 2.5, "cost": 0.0},
        "thisMonth": {"value": 3.5, "cost": 0.0},
        "thisYear": {"value": 4.5, "cost": 0.0},
    },
    "electricityOutLow": {
        "measurement": None,
        "thisDay": {"value": 1.09281, "cost": 0.0},
        "thisWeek": {"value": 2.0, "cost": 0.0},
        "thisMonth": {"value": 3.0, "cost": 0.0},
        "thisYear": {"value": 4.0, "cost": 0.0},
    },
    "gas": {
        "measurement": {
            "time": "2020-11-18T15:17:29.000Z",
            "rate": 0.0,
            "value": 0.0,
            "costPerHour": 0.0,
            "counterValue": 116.73000000002281,
        },
        "thisDay": {"value": 1.07, "cost": 0.642},
        "thisWeek": {"value": 5.634224386000001, "cost": 3.3805346316000007},
        "thisMonth": {"value": 39.14, "cost": 23.483999999999998},
        "thisYear": {"value": 116.73, "cost": 70.038},
    },
}

MOCK_LIMITED_CURRENT_MEASUREMENTS = {
    "electricity": {
        "measurement": {
            "time": "2020-11-18T15:17:24.000Z",
            "rate": 1011.6666666666667,
            "value": 0.0033333333333333335,
            "costPerHour": 0.20233333333333337,
            "counterValue": 409.17166666631937,
        },
        "thisDay": {"value": 3.296665869, "cost": 0.6593331738},
        "thisWeek": {"value": 17.509996085, "cost": 3.5019992170000003},
        "thisMonth": {"value": 103.28830788, "cost": 20.657661576000002},
        "thisYear": {"value": 672.9781177300001, "cost": 134.595623546},
    }
}
