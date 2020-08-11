"""Definitions shared by all numato tests."""

from numato_gpio import NumatoGpioError

NUMATO_CFG = {
    "numato": {
        "discover": ["/ttyACM0", "/ttyACM1"],
        "devices": [
            {
                "id": 0,
                "binary_sensors": {
                    "invert_logic": False,
                    "ports": {
                        "2": "numato_binary_sensor_mock_port2",
                        "3": "numato_binary_sensor_mock_port3",
                        "4": "numato_binary_sensor_mock_port4",
                    },
                },
                "sensors": {
                    "ports": {
                        "1": {
                            "name": "numato_adc_mock_port1",
                            "source_range": [100, 1023],
                            "destination_range": [0, 10],
                            "unit": "mocks",
                        }
                    },
                },
                "switches": {
                    "invert_logic": False,
                    "ports": {
                        "5": "numato_switch_mock_port5",
                        "6": "numato_switch_mock_port6",
                    },
                },
            }
        ],
    }
}


def mockup_raise(*args, **kwargs):
    """Mockup to replace regular functions for error injection."""
    raise NumatoGpioError("Error mockup")


def mockup_return(*args, **kwargs):
    """Mockup to replace regular functions for error injection."""
    return False
