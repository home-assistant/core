<p align="center">
  <a href="#"><img src="assets/smartir_climate.png" width="350" alt="SmartIR Climate"></a>
</p>

For this platform to work, we need a .json file containing all the necessary IR commands.
Find your device's brand code [here](CLIMATE.md#available-codes-for-climate-devices) and add the number in the `device_code` field. If your device is not working, you will need to learn your own codes and place the Json file in `smartir/codes/climate` subfolders. [Keite Trần](https://github.com/keitetran/BroadlinkIRTools) developed [an amazing web-based app](https://keitetran.github.io/BroadlinkIRTools/) for this job.
_Please note that the device_code field only accepts positive numbers. The .json extension is not required._

## Configuration variables:
**name** (Optional): The name of the device<br />
**unique_id** (Optional): An ID that uniquely identifies this device. If two devices have the same unique ID, Home Assistant will raise an exception.<br />
**device_code** (Required): .... (Accepts only positive numbers)<br />
**controller_data** (Required): The data required for the controller to function. Enter the entity_id of the Broadlink remote **(must be an already configured device)**, or the entity id of the Xiaomi IR controller, or the MQTT topic on which to send commands.<br />
**temperature_sensor** (Optional): *entity_id* for a temperature sensor<br />
**humidity_sensor** (Optional): *entity_id* for a humidity sensor<br />
**power_sensor** (Optional): *entity_id* for a sensor that monitors whether your device is actually On or Off. This may be a power monitor sensor. (Accepts only on/off states)<br />

## Example (using broadlink controller):
Add a Broadlink RM device named "Bedroom" via config flow (read the [docs](https://www.home-assistant.io/integrations/broadlink/)).

```yaml
smartir:

climate:
  - platform: smartir
    name: Office AC
    unique_id: office_ac
    device_code: 1000
    controller_data: remote.bedroom_remote
    temperature_sensor: sensor.temperature
    humidity_sensor: sensor.humidity
    power_sensor: binary_sensor.ac_power
```

## Example (using xiaomi controller):
```yaml
smartir:

remote:
  - platform: xiaomi_miio
    host: 192.168.10.10
    token: YOUR_TOKEN

climate:
  - platform: smartir
    name: Office AC
    unique_id: office_ac
    device_code: 2000
    controller_data: remote.xiaomi_miio_192_168_10_10
    temperature_sensor: sensor.temperature
    humidity_sensor: sensor.humidity
    power_sensor: binary_sensor.ac_power
```

## Example (using mqtt controller):
```yaml
smartir:

climate:
  - platform: smartir
    name: Office AC
    unique_id: office_ac
    device_code: 3000
    controller_data: home-assistant/office-ac/command
    temperature_sensor: sensor.temperature
    humidity_sensor: sensor.humidity
    power_sensor: binary_sensor.ac_power
```

## Example (using LOOKin controller):
```yaml
smartir:

climate:
  - platform: smartir
    name: Office AC
    unique_id: office_ac
    device_code: 4000
    controller_data: 192.168.10.10
    temperature_sensor: sensor.temperature
    humidity_sensor: sensor.humidity
    power_sensor: binary_sensor.ac_power
```

## Example (using ESPHome):
ESPHome configuration example:
```yaml
esphome:
  name: my_espir
  platform: ESP8266
  board: esp01_1m

api:
  services:
    - service: send_raw_command
      variables:
        command: int[]
      then:
        - remote_transmitter.transmit_raw:
            code: !lambda 'return command;'

remote_transmitter:
  pin: GPIO14
  carrier_duty_percent: 50%
```
HA configuration.yaml:
```yaml
smartir:

climate:
  - platform: smartir
    name: Office AC
    unique_id: office_ac
    device_code: 8000
    controller_data: my_espir_send_raw_command
    temperature_sensor: sensor.temperature
    humidity_sensor: sensor.humidity
    power_sensor: binary_sensor.ac_power
```

## Available codes for climate devices:
The following are the code files created by the amazing people in the community. Before you start creating your own code file, try if one of them works for your device. **Please open an issue if your device is working and not included in the supported models.**
Contributing to your own code files is welcome. However, we do not accept incomplete files as well as files related to MQTT controllers.

#### Toyotomi
| Code                               | Supported Models      | Controller |
| ---------------------------------- | --------------------- | ---------- |
| [1000](../codes/climate/1000.json) | AKIRA GAN/GAG-A128 VL | Broadlink  |

#### Panasonic
| Code                               | Supported Models                                                   | Controller |
| ---------------------------------- | ------------------------------------------------------------------ | ---------- |
| [1020](../codes/climate/1020.json) | CS-CE7HKEW<br>CS-CE9HKEW<br>CS-CE12HKEW<br>CS-PC24MKF<br>CS-C24PKF | Broadlink  |
| [1021](../codes/climate/1021.json) | CS-RE9GKE<br>CS-RE12GKE                                            | Broadlink  |
| [1022](../codes/climate/1022.json) | CS-Z25TK<br>CS-XN7SKJ                                              | Broadlink  |
| [1023](../codes/climate/1023.json) | CS-HE9JKE<br>CS-HE12JKE<br>CS-HE9LKE                               | Broadlink  |
| [1024](../codes/climate/1024.json) | CS-MRE7MKE                                                         | Broadlink  |
| [1025](../codes/climate/1025.json) | CS-E18FKR                                                          | Broadlink  |
| [1026](../codes/climate/1026.json) | CS-PC12QKT                                                         | Broadlink  |

#### General Electric
| Code                               | Supported Models                                                                               | Controller |
| ---------------------------------- | ---------------------------------------------------------------------------------------------- | ---------- |
| [1040](../codes/climate/1040.json) | Unknown model                                                                                  | Broadlink  |
| [1041](../codes/climate/1041.json) | AE1PH09IWF<br>AE0PH09IWO<br>AE1PH12IWF<br>AE0PH12IWO<br>AE4PH18IWF<br>AE4PH18IWF<br>AE5PH18IWO | Broadlink  |
| [1042](../codes/climate/1042.json) | ASHA09LCC                                                                                      | Broadlink  |
| [1043](../codes/climate/1043.json) | ASWX09LECA                                                                                     | Broadlink  |

#### LG
| Code                               | Supported Models                        | Controller |
| ---------------------------------- | --------------------------------------- | ---------- |
| [1060](../codes/climate/1060.json) | R09AWN<br>R24AWN<br>E09EK               | Broadlink  |
| [1061](../codes/climate/1061.json) | Unknown model                           | Broadlink  |
| [1062](../codes/climate/1062.json) | LG InverterV P12RK                      | Broadlink  |
| [1063](../codes/climate/1063.json) | LG Inverter P12EP1 (AKB74955603 Remote) | Broadlink  |
| [1064](../codes/climate/1064.json) | Unknown model                           | Broadlink  |
| [1065](../codes/climate/1065.json) | LG LA080EC,LAXXXEC (AKB73598011 remote) | Broadlink  |
| [3060](../codes/climate/3060.json) | G09LH                                   | Xiaomi     |

#### Hitachi
| Code                               | Supported Models                                              | Controller |
| ---------------------------------- | ------------------------------------------------------------- | ---------- |
| [1080](../codes/climate/1080.json) | Unknown model                                                 | Broadlink  |
| [1081](../codes/climate/1081.json) | RAC-10EH1<br>RAC-18EH1<br>RAS-10EH1<br>RAS-10EH3<br>RAS-18EH1 | Broadlink  |
| [1082](../codes/climate/1082.json) | RAS-25YHA<br>RAS-35YHA                                        | Broadlink  |
| [1083](../codes/climate/1083.json) | RAS-32CNH2                                                    | Broadlink  |
| [1084](../codes/climate/1084.json) | RAS-DX18HDK                                                   | Broadlink  |

#### Daikin
| Code                               | Supported Models                                                                                                                                               | Controller |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| [1100](../codes/climate/1100.json) | FTXS25CVMB<br>FTXS35CVMB<br>FTXS60BVMB<br>FVXS25BVMB                                                                                                           | Broadlink  |
| [1101](../codes/climate/1101.json) | FTXS20LVMA<br>FTXS25LVMA<br>FTXS35LVMA<br>FTXS46LVMA<br>FTXS50LVMA<br>FTXS60LVMA<br>FTXS71LVMA<br>FTXS85LVMA<br>FTXS95LVMA<br>FTXM35M<br>FVXM35F<br>FVXS50FV1B | Broadlink  |
| [1102](../codes/climate/1102.json) | FTV20AXV14                                                                                                                                                     | Broadlink  |
| [1103](../codes/climate/1103.json) | Unknown model                                                                                                                                                  | Broadlink  |
| [1104](../codes/climate/1104.json) | TF25DVM                                                                                                                                                        | Broadlink  |
| [1105](../codes/climate/1105.json) | FTX12NMVJU                                                                                                                                                     | Broadlink  |
| [1106](../codes/climate/1106.json) | ATX20KV1B<br>ATX25KV1B<br>ATX35KV1B                                                                                                                            | Broadlink  |
| [1107](../codes/climate/1107.json) | FTX25JAV1NB                                                                                                                                                    | Broadlink  |
| [3100](../codes/climate/3100.json) | FTXS25CVMB<br>FTXS35CVMB<br>FTXS60BVMB<br>FVXS25BVMB                                                                                                           | Xiaomi     |

#### Mitsubishi Electric
| Code                               | Supported Models                                                                                     | Controller |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------- | ---------- |
| [1120](../codes/climate/1120.json) | MSZ-GL25VGD<br>MSZ-GL35VGD<br>MSZ-GL42VGD<br>MSZ-GL50VG<br>MSZ-GL60VGD<br>MSZ-GL71VGD<br>MSZ-GL80VGD | Broadlink  
| [1121](../codes/climate/1121.json) | MSZ-GA35VA                                                                                           | Broadlink  
| [1122](../codes/climate/1122.json) | MSZ-AP50VGKD                                                                                         | Broadlink  
| [1123](../codes/climate/1123.json) | SRK25ZSX<br>SRC25ZSX                                                                                 | Broadlink  
| [1124](../codes/climate/1124.json) | MSZ-SF25VE3<br>MSZ-SF35VE3<br>MSZ-SF42VE3<br>MSZ-SF50VE<br>MSZ-AP20VG                                | Broadlink  
| [1125](../codes/climate/1125.json) | MLZ-KP25VF<br>MLZ-KP35VF<br>MLZ-KP50VF                                                               | Broadlink  
| [1126](../codes/climate/1126.json) | MSX09-NV II <br> MSH-07RV <br> MSH-12RV                                                              | Broadlink  
| [1127](../codes/climate/1127.json) | MSZ-HJ25VA                                                                                           | Broadlink  
| [1128](../codes/climate/1128.json) | MSZ-HJ35VA                                                                                           | Broadlink  
| [3129](../codes/climate/3129.json) | DXK18Z1-S                                                                                            | Xiaomi v2  

#### Actron
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1140](../codes/climate/1140.json) | Unknown model    | Broadlink  |

#### Carrier
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1160](../codes/climate/1160.json) | Unknown model    | Broadlink  |
| [1161](../codes/climate/1161.json) | 40GKX-024RB      | Broadlink  |

#### Gree
| Code                               | Supported Models | Controller                                      |
| ---------------------------------- | ---------------- | ----------------------------------------------- |
| [1180](../codes/climate/1180.json) | Unknown model    | Broadlink                                       |
| [1181](../codes/climate/1181.json) | Unknown model/Model: GWH09QB / YAN1F1 (Remote)    | Broadlink                                       |
| [1182](../codes/climate/1182.json) | Y512/Y502 (Remote)    | Broadlink                                       |
| [3180](../codes/climate/3180.json) | YB0FB2 (Remote)  | Xiaomi                                          |
| [3181](../codes/climate/3181.json) | YB1FA  (Remote)  | Xiaomi (v2)                                          |

#### Tosot
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1200](../codes/climate/1200.json) | Unknown model    | Broadlink  |

#### Sungold
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1220](../codes/climate/1220.json) | Unknown model    | Broadlink  |

#### Consul
| Code                               | Supported Models         | Controller |
| ---------------------------------- | ------------------------ | ---------- |
| [1240](../codes/climate/1240.json) | Unknown model            | Broadlink  |
| [1241](../codes/climate/1241.json) | CBV12CBBNA<br>CBY12DBBNA | Broadlink  |

#### Toshiba
| Code                               | Supported Models                                                                                                 | Controller |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ---------- |
| [1260](../codes/climate/1260.json) | RAS-13NKV-E / RAS-13NAV-E<br>RAS-13NKV-A / RAS-13NAV-A<br>RAS-16NKV-E / RAS-16NAV-E<br>RAS-16NKV-A / RAS-16NAV-A | Broadlink  |
| [1261](../codes/climate/1261.json) | WH-TA05NE                                                                                                        | Broadlink  |
| [7260](../codes/climate/7260.json) | RAS-18NKV2-E                                                                                                     | ESPHome    |

#### Fujitsu
| Code                               | Supported Models                            | Controller |
| ---------------------------------- | ------------------------------------------- | ---------- |
| [1280](../codes/climate/1280.json) | AR-RBE1E (Remote control)                   | Broadlink  |
| [1281](../codes/climate/1281.json) | AR-RY3 (Remote control)<br>AR-RAE1/AR-RAE1E | Broadlink  |
| [1282](../codes/climate/1282.json) | AR-JW11 (Remote control)                    | Broadlink  |
| [1283](../codes/climate/1283.json) | AR-AB5 (Remote control)                     | Broadlink  |
| [1284](../codes/climate/1284.json) | AR-REG1U (Remote control)                   | Broadlink  |
| [1285](../codes/climate/1285.json) | AR-RCE1E (Remote control)                   | Broadlink  |
| [3285](../codes/climate/3285.json) | AR-RCE1E (Remote control)                   | Xiaomi (v2)|
| [7285](../codes/climate/7285.json) | AR-RCE1E (Remote control)                   | ESPHome    |
| [1286](../codes/climate/1286.json) | AR-JE5 (Remote control)                     | Broadlink  |
| [1287](../codes/climate/1287.json) | AR-REB1E (Remote control)                   | Broadlink  |
| [1288](../codes/climate/1288.json) | AR-REB1E (Remote control)                   | Broadlink  |

#### Sharp
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1300](../codes/climate/1300.json) | AY-B22DM         | Broadlink  |

#### Haier
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1320](../codes/climate/1320.json) | Unknown model    | Broadlink  |

#### Tadiran
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1340](../codes/climate/1340.json) | Unknown model    | Broadlink  |

#### Springer
| Code                               | Supported Models       | Controller |
| ---------------------------------- | ---------------------- | ---------- |
| [1360](../codes/climate/1360.json) | Split Hi Wall Maxiflex | Broadlink  |

#### Midea
| Code                               | Supported Models               | Controller |
| ---------------------------------- | ------------------------------ | ---------- |
| [1380](../codes/climate/1380.json) | Unknown model                  | Broadlink  |
| [1381](../codes/climate/1381.json) | Unknown model                  | Broadlink  |
| [1382](../codes/climate/1382.json) | MSY-12HRDN1                    | Broadlink  |
| [1383](../codes/climate/1383.json) | KFR-35G                        | Broadlink  |
| [3380](../codes/climate/3380.json) | MCD-24HRN1-Q1<br>RAS-10N3KVR-E | Xiaomi     |

#### Samsung
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1400](../codes/climate/1400.json) | Unknown model    | Broadlink  |
| [1401](../codes/climate/1401.json) | AR##HSF/JFS##    | Broadlink  |

#### Sintech
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1420](../codes/climate/1420.json) | KFR-34GW         | Broadlink  |

#### Akai
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1440](../codes/climate/1440.json) | Unknown model    | Broadlink  |

#### Alliance
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1460](../codes/climate/1460.json) | Unknown model    | Broadlink  |

#### Junkers
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1480](../codes/climate/1480.json) | Excellence       | Broadlink  |

#### Sanyo
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1500](../codes/climate/1500.json) | Unknown          | Broadlink  |
| [1501](../codes/climate/1501.json) | SAP-KR124EHEA    | Broadlink  |

#### Hisense
| Code                               | Supported Models   | Controller |
| ---------------------------------- | ------------------ | ---------- |
| [1520](../codes/climate/1520.json) | Unknown            | Broadlink  |
| [1521](../codes/climate/1521.json) | Unknown            | Broadlink  |
| [1522](../codes/climate/1522.json) | DG11R2-01 (Remote) | Broadlink  |
| [5520](../codes/climate/5520.json) | AS-07UR4SYDD815G   | LOOKin  |

#### Whirlpool
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1540](../codes/climate/1540.json) | SPIS412L         | Broadlink  |

#### Tadiran
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1560](../codes/climate/1560.json) | WIND 3P          | Broadlink  |

#### Chigo
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1580](../codes/climate/1580.json) | ZH/JT-03 (Remote)| Broadlink  |
| [3580](../codes/climate/3580.json) | Unknown          | Xiaomi (v2)|

#### Beko
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1600](../codes/climate/1600.json) | BEVCA 120        | Broadlink  |

#### Tornado
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1620](../codes/climate/1620.json) | Unknown          | Broadlink  |
| [1621](../codes/climate/1621.json) | Super Legend 40  | Broadlink  |

#### Fujiko
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1640](../codes/climate/1640.json) | Unknown          | Broadlink  |

#### Royal
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1660](../codes/climate/1660.json) | 08HPN1T1         | Broadlink  |

#### Mitsubishi Heavy
| Code                               | Supported Models                                     | Controller |
| ---------------------------------- | ---------------------------------------------------- | ---------- |
| [1680](../codes/climate/1680.json) | SRK25ZJ-S1                                           | Broadlink  |
| [1681](../codes/climate/1681.json) | SRK71ZK-S                                            | Broadlink  |
| [1682](../codes/climate/1681.json) | SRKM25H<br>SRK40HBE                                  | Broadlink  |
| [1683](../codes/climate/1683.json) | DXK12ZMA-S                                           | Broadlink  |
| [1684](../codes/climate/1684.json) | DXK24ZRA                                             | Broadlink  |
| [1685](../codes/climate/1685.json) | SRK50ZS-S                                            | Broadlink  |
| [1686](../codes/climate/1685.json) | SRK20ZSA-W<br>SRK25ZSA-W<br>SRK35ZSA-W<br>SRK50ZSA-W | Broadlink  |
| [1687](../codes/climate/1687.json) | SRK35ZJX-S                                           | Broadlink  |

#### Electrolux
| Code                               | Supported Models                                                                                                                                                                             | Controller |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| [1700](../codes/climate/1700.json) | EACS/I-HAT/N3                                                                                                                                                                                | Broadlink  |
| [1701](../codes/climate/1701.json) | EACS-HA                                                                                                                                                                                      | Broadlink  |
| [1702](../codes/climate/1702.json) | QI/QE09F<br>QI/QE09R<br>QI/QE12F<br>QI/QE12R<br>QI/QE18F<br>QI/QE18R<br>QI/QE22F<br>QI/QE22R<br>XI/XE09F<br>XI/XE09R<br>XI/XE12F<br>XI/XE12R<br>XI/XE18F<br>XI/XE18R<br>XI/XE22F<br>XI/XE22R | Broadlink  |

#### Erisson
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1720](../codes/climate/1720.json) | EC-S07T2         | Broadlink  |

#### Kelvinator
| Code                               | Supported Models              | Controller |
| ---------------------------------- | ----------------------------- | ---------- |
| [1740](../codes/climate/1740.json) | KSV25HRG (RG57A6/BGEF Remote) | Broadlink  |
| [7740](../codes/climate/7740.json) | KSV25HWH                      | ESPHome    |

#### Daitsu
| Code                               | Supported Models                      | Controller |
| ---------------------------------- | ------------------------------------- | ---------- |
| [1760](../codes/climate/1760.json) | DS12U-RV (or any using R51M/E remote) | Broadlink  |
| [1761](../codes/climate/1761.json) | DS-9KIDT                              | Broadlink  |
| [1762](../codes/climate/1762.json) | ASD9KI-DT                             | Broadlink  |

#### Trotec
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1780](../codes/climate/1780.json) | YX1F6 (Remote)   | Broadlink  |
| [1781](../codes/climate/1781.json) | YX1F (Remote)   | Broadlink  |

#### BALLU
| Code                               | Supported Models    | Controller |
| ---------------------------------- | ------------------- | ---------- |
| [1800](../codes/climate/1800.json) | YKR-K/002E (Remote) | Broadlink  |

#### Riello
| Code                               | Supported Models  | Controller |
| ---------------------------------- | ----------------- | ---------- |
| [1820](../codes/climate/1820.json) | WSI XN<br>RAR-3U4 | Broadlink  |

#### Hualing
| Code                               | Supported Models            | Controller |
| ---------------------------------- | --------------------------- | ---------- |
| [1840](../codes/climate/1840.json) | KFR-45GW/JNV<br>KFR-45G/JNV | Broadlink  |

#### Simbio
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1860](../codes/climate/1860.json) | Unknown          | Broadlink  |

#### Saunier Duval
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1880](../codes/climate/1880.json) | Unknown          | Broadlink  |

#### TCL
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1900](../codes/climate/1900.json) | TAC-12CHSD/XA21I | Broadlink  |

#### Aokesi
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1920](../codes/climate/1920.json) | Unknown          | Broadlink  |

#### Electra
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1940](../codes/climate/1940.json) | Unknown          | Broadlink  |
| [1941](../codes/climate/1941.json) | iGo              | Broadlink  |
| [1942](../codes/climate/1942.json) | Electra Classic  | Broadlink  |

#### AUX
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1960](../codes/climate/1960.json) | Unknown          | Broadlink  |

#### Fuji
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [1980](../codes/climate/1980.json) | Unknown          | Broadlink  |

#### Aeronik
| Code                               | Supported Models     | Controller |
| ---------------------------------- | -------------------- | ---------- |
| [2000](../codes/climate/2000.json) | ASO-12IL<br>ASI-12IL | Broadlink  |

#### Ariston
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [2020](../codes/climate/2020.json) | A-IFWHxx-IGX     | Broadlink  |

#### Pioneer
| Code                               | Supported Models                 | Controller |
| ---------------------------------- | -------------------------------- | ---------- |
| [2040](../codes/climate/2040.json) | WYS018GMFI17RL<br>WYS009GMFI17RL<br>CB018GMFILCFHD<br>CB012GMFILCFHD | Broadlink  |

#### Dimplex
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [2060](../codes/climate/2060.json) | GDPAC12RC        | Broadlink  |

#### Sendo
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [2080](../codes/climate/2080.json) | SND-18IK         | Broadlink  |

#### Mirage
| Code                               | Supported Models   | Controller |
| ---------------------------------- | ------------------ | ---------- |
| [2100](../codes/climate/2100.json) | Magnum Inverter 19 | Broadlink  |

#### Technibel
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [2120](../codes/climate/2120.json) | MPAF13A0R5IAA    | Broadlink  |

#### Unionaire
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [2140](../codes/climate/2140.json) | Artify           | Broadlink  |

#### Lennox
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [2160](../codes/climate/2160.json) | Unknown          | Broadlink  |

#### Hokkaido
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [2180](../codes/climate/2180.json) | LA09-DUAL H1     | Broadlink  |

#### IGC
| Code                               | Supported Models   | Controller |
| ---------------------------------- | ------------------ | ---------- |
| [2200](../codes/climate/2200.json) | RAK-12NH<br>RAK-18NH | Broadlink  |

#### Blueridge
| Code                               | Supported Models | Controller |
| ---------------------------------- | ---------------- | ---------- |
| [2220](../codes/climate/2220.json) | RG57A4<br>BGEFU1 | Broadlink  |

#### Delonghi
| Code                               | Supported Models        | Controller |
| ---------------------------------- | ----------------------- | ---------- |
| [2240](../codes/climate/2240.json) | PAC N82ECO<br>PAC AN111 | Broadlink  |

#### Profio
| Code                               | Supported Models        | Controller |
| ---------------------------------- | ----------------------- | ---------- |
| [2260](../codes/climate/2260.json) | Unknown                 | Broadlink  |

#### Hantech
| Code                               | Supported Models        | Controller |
| ---------------------------------- | ----------------------- | ---------- |
| [2280](../codes/climate/2280.json) | A018-12KR2              | Broadlink  |
| [2281](../codes/climate/2281.json) | A016-09KR2/A            | Broadlink  |

#### Zanussi
| Code                               | Supported Models        | Controller |
| ---------------------------------- | ----------------------- | ---------- |
| [2300](../codes/climate/2300.json) | ZH/TT-02 (Remote)       | Broadlink  |

#### Whynter
| Code                               | Supported Models       | Controller |
| ---------------------------------- | ---------------------- | ---------- |
| [2320](../codes/climate/2320.json) | ARC-126MD / ARC-126MDB | Broadlink  |

#### Vortex
| Code                               | Supported Models       | Controller |
| ---------------------------------- | ---------------------- | ---------- |
| [2340](../codes/climate/2340.json) | VOR-12C3/407           | Broadlink  |

#### Flouu
| Code                               | Supported Models       | Controller |
| ---------------------------------- | ---------------------- | ---------- |
| [2360](../codes/climate/2360.json) | Unknown                | Broadlink  |

#### Baxi
| Code                               | Supported Models       | Controller |
| ---------------------------------- | ---------------------- | ---------- |
| [2380](../codes/climate/2380.json) | Unknown                | Broadlink  |

#### Yamatsu
| Code                               | Supported Models       | Controller |
| ---------------------------------- | ---------------------- | ---------- |
| [2400](../codes/climate/2400.json) | YAM-12KDA              | Broadlink  |

#### VS
| Code                               | Supported Models       | Controller |
| ---------------------------------- | ---------------------- | ---------- |
| [2420](../codes/climate/2420.json) | YKR-F06                | Broadlink  |

#### Vaillant
| Code                               | Supported Models       | Controller |
| ---------------------------------- | ---------------------- | ---------- |
| [2440](../codes/climate/2440.json) | ClimaVair VAI 8-025    | Broadlink  |
