"""Const Freedompro for test."""

DEVICES = [
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*2VAS3HTWINNZ5N6HVEIPDJ6NX85P2-AM-GSYWUCNPU0",
        "name": "Bathroom leak sensor",
        "type": "leakSensor",
        "characteristics": ["leakDetected"],
    },
    {
        "uid": "2WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*2VAS3HTWINNZ5N6HVEIPDJ6NX85P2-AM-GSYWUCNPU0",
        "name": "lock",
        "type": "lock",
        "characteristics": ["lock"],
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*ILYH1E3DWZOVMNEUIMDYMNLOW-LFRQFDPWWJOVHVDOS",
        "name": "bedroom",
        "type": "fan",
        "characteristics": ["on", "rotationSpeed"],
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*SOT3NKALCRQMHUHJUF79NUG6UQP1IIQIN1PJVRRPT0C",
        "name": "Contact sensor living room",
        "type": "contactSensor",
        "characteristics": ["contactSensorState"],
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*VTEPEDYE8DXGS8U94CJKQDLKMN6CUX1IJWSOER2HZCK",
        "name": "Doorway motion sensor",
        "type": "motionSensor",
        "characteristics": ["motionDetected"],
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*QN-DDFMPEPRDOQV7W7JQG3NL0NPZGTLIBYT3HFSPNEY",
        "name": "Garden humidity sensor",
        "type": "humiditySensor",
        "characteristics": ["currentRelativeHumidity"],
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*1JKU1MVWHQL-Z9SCUS85VFXMRGNDCDNDDUVVDKBU31W",
        "name": "Irrigation switch",
        "type": "switch",
        "characteristics": ["on"],
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*JHJZIZ9ORJNHB7DZNBNAOSEDECVTTZ48SABTCA3WA3M",
        "name": "lightbulb",
        "type": "lightbulb",
        "characteristics": ["on", "brightness", "saturation", "hue"],
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*SNG7Y3R1R0S_W5BCNPP1O5WUN2NCEOOT27EFSYT6JYS",
        "name": "Living room occupancy sensor",
        "type": "occupancySensor",
        "characteristics": ["occupancyDetected"],
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*LWPVY7X1AX0DRWLYUUNZ3ZSTHMYNDDBQTPZCZQUUASA",
        "name": "Living room temperature sensor",
        "type": "temperatureSensor",
        "characteristics": ["currentTemperature"],
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*SXFMEXI4UMDBAMXXPI6LJV47O9NY-IRCAKZI7_MW0LY",
        "name": "Smoke sensor kitchen",
        "type": "smokeSensor",
        "characteristics": ["smokeDetected"],
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*R6V0FNNF7SACWZ8V9NCOX7UCYI4ODSYAOJWZ80PLJ3C",
        "name": "Bedroom CO2 sensor",
        "type": "carbonDioxideSensor",
        "characteristics": ["carbonDioxideDetected", "carbonDioxideLevel"],
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*3-QURR5Q6ADA8ML1TBRG59RRGM1F9LVUZLKPYKFJQHC",
        "name": "bedroomlight",
        "type": "lightbulb",
        "characteristics": ["on"],
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*TWMYQKL3UVED4HSIIB9GXJWJZBQCXG-9VE-N2IUAIWI",
        "name": "thermostat",
        "type": "thermostat",
        "characteristics": [
            "heatingCoolingState",
            "currentTemperature",
            "targetTemperature",
        ],
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*3XSSVIJWK-65HILWTC4WINQK46SP4OEZRCNO25VGWAS",
        "name": "blind",
        "type": "windowCovering",
        "characteristics": ["position"],
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*JVRAR_6WVL1Y0PJ5GFWGPMFV7FLVD4MZKBWXC_UFWYM",
        "name": "Garden light sensors",
        "type": "lightSensor",
        "characteristics": ["currentAmbientLightLevel"],
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*0PUTVZVJJJL-ZHZZBHTIBS3-J-U7JYNPACFPJW0MD-I",
        "name": "Living room outlet",
        "type": "outlet",
        "characteristics": ["on"],
    },
]

DEVICES_STATE = [
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*2VAS3HTWINNZ5N6HVEIPDJ6NX85P2-AM-GSYWUCNPU0",
        "type": "leakSensor",
        "state": {"leakDetected": 0},
        "online": True,
    },
    {
        "uid": "2WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*2VAS3HTWINNZ5N6HVEIPDJ6NX85P2-AM-GSYWUCNPU0",
        "type": "lock",
        "state": {"lock": 0},
        "online": True,
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*ILYH1E3DWZOVMNEUIMDYMNLOW-LFRQFDPWWJOVHVDOS",
        "type": "fan",
        "state": {"on": False, "rotationSpeed": 0},
        "online": True,
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*SOT3NKALCRQMHUHJUF79NUG6UQP1IIQIN1PJVRRPT0C",
        "type": "contactSensor",
        "state": {"contactSensorState": False},
        "online": True,
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*VTEPEDYE8DXGS8U94CJKQDLKMN6CUX1IJWSOER2HZCK",
        "type": "motionSensor",
        "state": {"motionDetected": False},
        "online": True,
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*QN-DDFMPEPRDOQV7W7JQG3NL0NPZGTLIBYT3HFSPNEY",
        "type": "humiditySensor",
        "state": {"currentRelativeHumidity": 0},
        "online": True,
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*1JKU1MVWHQL-Z9SCUS85VFXMRGNDCDNDDUVVDKBU31W",
        "type": "switch",
        "state": {"on": False},
        "online": True,
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*JHJZIZ9ORJNHB7DZNBNAOSEDECVTTZ48SABTCA3WA3M",
        "type": "lightbulb",
        "state": {"on": True, "brightness": 0, "saturation": 0, "hue": 0},
        "online": True,
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*SNG7Y3R1R0S_W5BCNPP1O5WUN2NCEOOT27EFSYT6JYS",
        "type": "occupancySensor",
        "state": {"occupancyDetected": False},
        "online": True,
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*LWPVY7X1AX0DRWLYUUNZ3ZSTHMYNDDBQTPZCZQUUASA",
        "type": "temperatureSensor",
        "state": {"currentTemperature": 0},
        "online": True,
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*SXFMEXI4UMDBAMXXPI6LJV47O9NY-IRCAKZI7_MW0LY",
        "type": "smokeSensor",
        "state": {"smokeDetected": False},
        "online": True,
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*R6V0FNNF7SACWZ8V9NCOX7UCYI4ODSYAOJWZ80PLJ3C",
        "type": "carbonDioxideSensor",
        "state": {"carbonDioxideDetected": False, "carbonDioxideLevel": 0},
        "online": True,
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*3-QURR5Q6ADA8ML1TBRG59RRGM1F9LVUZLKPYKFJQHC",
        "type": "lightbulb",
        "state": {"on": False},
        "online": True,
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*TWMYQKL3UVED4HSIIB9GXJWJZBQCXG-9VE-N2IUAIWI",
        "type": "thermostat",
        "state": {
            "heatingCoolingState": 1,
            "currentTemperature": 14,
            "targetTemperature": 14,
        },
        "online": True,
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*3XSSVIJWK-65HILWTC4WINQK46SP4OEZRCNO25VGWAS",
        "type": "windowCovering",
        "state": {"position": 0},
        "online": True,
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*JVRAR_6WVL1Y0PJ5GFWGPMFV7FLVD4MZKBWXC_UFWYM",
        "type": "lightSensor",
        "state": {"currentAmbientLightLevel": 0},
        "online": True,
    },
    {
        "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*0PUTVZVJJJL-ZHZZBHTIBS3-J-U7JYNPACFPJW0MD-I",
        "type": "outlet",
        "state": {"on": False},
        "online": True,
    },
]
