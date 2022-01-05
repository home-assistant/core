"""All response from flashforge printers."""

# InfoRequest
MACHINE_INFO = (
    "CMD M115 Received.\r\n"
    "Machine Type: Flashforge Adventurer 4\r\n"
    "Machine Name: Adventurer4\r\n"
    "Firmware: v2.0.9\r\n"
    "SN: SNADVA1234567\r\n"
    "X: 220 Y: 200 Z: 250\r\n"
    "Tool Count: 1\r\n"
    "Mac Address:88:A9:A7:93:86:F8\n \r\n"
    "ok\r\n"
)

# ProgressRequest
PROGRESS_READY = "CMD M27 Received.\r\nSD printing byte 0/100\r\nok\r\n"
PROGRESS_PRINTING = (
    "CMD M27 Received.\r\nSD printing byte 11/100\r\nLayer: 44/419\r\nok\r\n"
)

# TempRequest
TEMP_READY = "CMD M105 Received.\r\nT0:22/0 B:14/0\r\nok\r\n"
TEMP_PRINTING = "CMD M105 Received.\r\nT0:198/210 B:48/64\r\nok\r\n"

# StatusRequest
STATUS_READY = (
    "CMD M119 Received.\r\n"
    "Endstop: X-max:0 Y-max:0 Z-max:0\r\n"
    "MachineStatus: READY\r\n"
    "MoveMode: READY\r\n"
    "Status: S:1 L:0 J:0 F:0\r\n"
    "LED: 0\r\n"
    "CurrentFile: \r\n"
    "ok\r\n"
)

STATUS_PRINTING = (
    "CMD M119 Received.\r\n"
    "Endstop: X-max:0 Y-max:0 Z-max:0\r\n"
    "MachineStatus: BUILDING_FROM_SD\r\n"
    "MoveMode: MOVING\r\n"
    "Status: S:1 L:0 J:0 F:0\r\n"
    "LED: 1\r\n"
    "CurrentFile: RussianDollMazeModels.gx\r\n"
    "ok\r\n"
)
