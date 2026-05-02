# WJG XM-3820 Camera Bridge

Lokale Home-Assistant-Integration fuer WJG/Tenganda/XM-basierte Smartcams.

## Funktionen

- RTSP-Livestream
- Snapshot (HTTP)
- Aufnahme Start/Stop (XM SDK + HTTP-Fallback)
- PTZ-Steuerung (Buttons)
- Bewegungssensor
- Dateilisten-Sensor
- ONVIF-Basisfunktionen (Stream/PTZ)
- ADB-Proxy-Modus (localhost 8080/8081)

## Kompatibilitaet

Diese Integration ist fuer XM/Xiongmai-aehnliche Kameras ausgelegt, z. B. Modelle mit:

- iCam365 App
- Ports 80/554/34567
- RTSP-Pfaden wie `/user=admin&password=&channel=1&stream=0.sdp?real_stream`

Hinweis: Bei OEM-Varianten koennen RTSP-/Snapshot-Pfade und PTZ/Recording-Endpunkte abweichen.

## Einrichtung

1. Integration in HACS installieren
2. Home Assistant neu starten
3. Integration in Home Assistant hinzufuegen
4. Host/Ports/Protokoll eintragen

## Wichtige Entitaeten

- `camera.*` Livestream + Snapshot
- `switch.*_recording` Aufnahme
- `binary_sensor.*_motion` Bewegung
- `button.*_ptz_*` PTZ
- `sensor.*_filelist` Dateiliste

## Optionen

- `protocol`
- `rtsp_path`
- `snapshot_path`
- `http_retries` (0-5)

## Support

Wenn etwas nicht funktioniert, bitte ein Issue mit folgenden Infos erstellen:

- Kameramodell/OEM
- Firmware (falls bekannt)
- verwendete Pfade/Ports
- relevante Home-Assistant-Logs
