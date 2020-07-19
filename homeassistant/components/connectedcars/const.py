"""Constants for the ConnectedCars.io integration."""

DOMAIN = "connectedcars"

CONNECTED_CARS_CLIENT = "connectec_cars_client"

CONF_NAMESPACE = "namespace"
CONF_VIN = "config_vin"

ATTR_IDENTIFIERS = "identifiers"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MODEL = "model"

ICONS = {
    "range sensor": "mdi:gauge",
    "mileage sensor": "mdi:counter",
    "update switch": "mdi:update",
    "maxrange switch": "mdi:gauge-full",
    "temperature sensor": "mdi:thermometer",
    "location tracker": "mdi:crosshairs-gps",
}


COMPLETE_QUERY = """query User{
  viewer {
    id
    firstname
    lastname
    email
    vehicles {
      vehicle {
        id
        vin
        class
        brand
        make
        model
        name
        licensePlate
        fuelType
        fuelLevel {
            liter
        }
        fuelPercentage {
            percent
        }
        odometer {
            odometer
        }
        position{
            latitude
            longitude
        }
        refuelEvents {
            litersDifference
            time
        }
        latestBatteryVoltage {
            voltage
        }
        health {
            ok
            recommendation
            lamp {
                lampDetails {
                    title
                }
            }
        }
        trips (last:3){
            items {
                duration
                fuelUsed
                mileage
                startLongitude
                startLatitude
                endLongitude
                endLatitude
            }
        }
      }
    }
  }
}"""

ATTR_API_USER_FIRSTNAME = "first_name"
ATTR_API_USER_LASTNAME = "last_name"
ATTR_API_USER_EMAIL = "email"

ATTR_API_VEHICLE_ID = "vehicle_id"
ATTR_API_VEHICLE_VIN = "vehicle_vin"
ATTR_API_VEHICLE_MAKE = "vehicle_make"
ATTR_API_VEHICLE_MODEL = "vehicle_model"
ATTR_API_VEHICLE_NAME = "vehicle_name"
ATTR_API_VEHICLE_LICENSEPLATE = "vehicle_license_plate"
ATTR_API_VEHICLE_FUELLEVEL = "vehicle_fuel_level"
ATTR_API_VEHICLE_FUELPERCENTAGE = "vehicle_fuel_percentage"
ATTR_API_VEHICLE_ODOMETER = "vehicle_odometer"
ATTR_API_VEHICLE_VOLTAGE = "vehicle_voltage"

ATTR_API_VEHICLE_POS_LATITUDE = "vehicle_position_latitude"
ATTR_API_VEHICLE_POS_LONGITUDE = "vehicle_position_longitude"
