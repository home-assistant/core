"""Constants for Discovergy integration tests."""
import datetime

from pydiscovergy.models import Meter, Reading

GET_METERS = [
    Meter(
        meterId="f8d610b7a8cc4e73939fa33b990ded54",
        serialNumber="abc123",
        fullSerialNumber="abc123",
        type="TST",
        measurementType="ELECTRICITY",
        loadProfileType="SLP",
        location={
            "city": "Testhause",
            "street": "Teststraße",
            "streetNumber": "1",
            "country": "Germany",
        },
        manufacturerId="TST",
        printedFullSerialNumber="abc123",
        administrationNumber="12345",
        scalingFactor=1,
        currentScalingFactor=1,
        voltageScalingFactor=1,
        internalMeters=1,
        firstMeasurementTime=1517569090926,
        lastMeasurementTime=1678430543742,
    ),
]

LAST_READING = Reading(
    time=datetime.datetime(2023, 3, 10, 7, 32, 6, 702000),
    values={
        "energy": 119348699715000.0,
        "energy1": 2254180000.0,
        "energy2": 119346445534000.0,
        "energyOut": 55048723044000.0,
        "energyOut1": 0.0,
        "energyOut2": 0.0,
        "power": 531750.0,
        "power1": 142680.0,
        "power2": 138010.0,
        "power3": 251060.0,
        "voltage1": 239800.0,
        "voltage2": 239700.0,
        "voltage3": 239000.0,
    },
)
