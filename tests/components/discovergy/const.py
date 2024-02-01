"""Constants for Discovergy integration tests."""
import datetime

from pydiscovergy.models import Location, Meter, Reading

GET_METERS = [
    Meter(
        meter_id="f8d610b7a8cc4e73939fa33b990ded54",
        serial_number="abc123",
        full_serial_number="abc123",
        type="TST",
        measurement_type="ELECTRICITY",
        load_profile_type="SLP",
        location=Location(
            zip=12345,
            city="Testhause",
            street="Teststraße",
            street_number="1",
            country="Germany",
        ),
        additional={
            "manufacturer_id": "TST",
            "printed_full_serial_number": "abc123",
            "administration_number": "12345",
            "scaling_factor": 1,
            "current_scaling_factor": 1,
            "voltage_scaling_factor": 1,
            "internal_meters": 1,
            "first_measurement_time": 1517569090926,
            "last_measurement_time": 1678430543742,
        },
    ),
    Meter(
        meter_id="d81a652fe0824f9a9d336016587d3b9d",
        serial_number="def456",
        full_serial_number="def456",
        type="PIP",
        measurement_type="GAS",
        load_profile_type="SLP",
        location=Location(
            zip=12345,
            city="Testhause",
            street="Teststraße",
            street_number="1",
            country="Germany",
        ),
        additional={
            "manufacturer_id": "TST",
            "printed_full_serial_number": "def456",
            "administration_number": "12345",
            "scaling_factor": 1,
            "current_scaling_factor": 1,
            "voltage_scaling_factor": 1,
            "internal_meters": 1,
            "first_measurement_time": 1517569090926,
            "last_measurement_time": 1678430543742,
        },
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
        "power": 0.0,
        "power1": 142680.0,
        "power2": 138010.0,
        "power3": 251060.0,
        "voltage1": 239800.0,
        "voltage2": 239700.0,
        "voltage3": 239000.0,
    },
)

LAST_READING_GAS = Reading(
    time=datetime.datetime(2023, 3, 10, 7, 32, 6, 702000),
    values={"actualityDuration": 52000.0, "storageNumber": 0.0, "volume": 21064800.0},
)
