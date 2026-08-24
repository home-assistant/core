# Haus-Bus Home Assistant Integration – Kontextdatei

## Überblick

Die **hausbus**-Integration verbindet Home Assistant mit dem [haus-bus.de](https://www.haus-bus.de) Bussystem.
Sie ist ein lokal-push-basiertes (kein Cloud-Zwang, kein Polling) System, das per UDP-Broadcast mit den haus-bus.de-Modulen kommuniziert.

Aktuell implementiert: **Cover (Rollladen)**

---

## Verzeichnisstruktur

```
homeassistant/components/hausbus/   ← Integration
    __init__.py                     ← Entry-Setup, Platform-Forward
    config_flow.py                  ← Config Flow (Geräteerkennung)
    const.py                        ← Konstanten (DOMAIN, Signals)
    cover.py                        ← Cover-Plattform (Rollladen)
    entity.py                       ← Basis-Entity (HausbusEntity)
    gateway.py                      ← Gateway (HausbusGateway, async_get_home_server)
    manifest.json                   ← Integration-Metadaten
    quality_scale.yaml              ← Qualitätsstufen-Status (Bronze target)
    strings.json                    ← UI-Strings für Config Flow

tests/components/hausbus/
    conftest.py                     ← Fixtures (mock_home_server)
    test_config_flow.py             ← Tests für den Config Flow
    test_cover.py                   ← Tests für die Cover-Plattform
    test_gateway.py                 ← Tests für den Gateway
    test_init.py                    ← Tests für __init__

PyHausBus-main/                    ← Python-Bibliothek für haus-bus.de
    pyhausbus/
        HomeServer.py               ← Singleton, verwaltet Geräteentdeckung
        BusHandler.py               ← UDP-Socket, Broadcast-Kommunikation (Singleton)
        ABusFeature.py              ← Basisklasse für alle haus-bus.de Kanäle
        ObjectId.py                 ← Adressierung: deviceId + classId + instanceId
        IBusDataListener.py         ← Interface für Datenempfang
        IBusDeviceListener.py       ← Interface für neue Geräte
        ResultWorker.py             ← Verarbeitung eingehender Kommandos
        de/hausbus/homeassistant/proxy/
            Rollladen.py            ← Cover-Kanal (Klasse für Rolladen-Steuerung)
            rollladen/data/         ← Empfangene Ereignisse/Status-Objekte
            rollladen/params/       ← Enums (EDirection, EErrorCode, ENewState)
            Controller.py           ← Geräte-Controller für Entdeckung
            ProxyFactory.py         ← Mapping classId → Klassenname
```

---

## Wichtige Konzepte

### Kommunikation (lokal_push)
- **UDP-Broadcast** auf Port (definiert in `HausBusUtils.UDP_PORT`), kein zentraler Server
- `BusHandler` (Singleton): sendet und empfängt UDP-Pakete, benachrichtigt registrierte `IBusDataListener`
- `HomeServer` (Singleton): registriert sich als `IBusDataListener`, orchestriert Geräteentdeckung

### Adressierung: `ObjectId`
Jeder Kanal eines Geräts hat eine 32-Bit-`objectId`, die aus drei Teilen besteht:
- `deviceId` – eindeutige Geräte-ID
- `classId` – Typ des Kanals (z.B. `18` = Rollladen)
- `instanceId` – Instanznummer am Gerät (z.B. `1`, `2`)

```python
# Hilfsfunktion aus HausBusUtils:
objectId = HausBusUtils.getObjectId(deviceId, classId, instanceId)
```

### Geräteentdeckung (Discovery)
1. `HomeServer.searchDevices()` sendet `getModuleId`-Broadcast an alle Gruppen
2. Geräte antworten mit `ModuleId`, `BusHandler` leitet an `HomeServer.busDataReceived` weiter
3. `DeviceCollector` sammelt Antworten, übergibt nach 0.5s Timeout an `DeviceWorker`
4. `DeviceWorker` fragt Konfiguration (`getConfiguration`) und Remote-Objekte (`getRemoteObjects`) ab
5. `DeviceWorker.getHomeassistantChannels()` baut `ABusFeature`-Instanzen der Kanäle, setzt Namen aus Templates
6. Für jeden Listener (`IBusDeviceListener`) wird `newDeviceDetected()` aufgerufen

### Dispatcher-Signale (Thread-Sicherheit)
- **`NEW_CHANNEL_ADDED`** (`"hausbus_channel_added"`): neuer Kanal entdeckt → Platform erstellt Entity
- **`"hausbus_update_{objectId}"`**: Zustandsänderung für einen konkreten Kanal

Da `busDataReceived` und `newDeviceDetected` aus Hintergrundthreads aufgerufen werden, wird  
`hass.loop.call_soon_threadsafe(async_dispatcher_send, ...)` verwendet.

---

## Architektur der Integration

### `__init__.py`
- Definiert `HausbusConfigEntry = ConfigEntry[HausbusGateway]` (typed alias)
- `async_setup_entry`: erstellt `HausbusGateway`, startet Discovery per `hass.async_create_task`
- `async_unload_entry`: meldet Listener vom `HomeServer` ab, entlädt Plattformen

### `config_flow.py` (`HausBusConfigFlow`)
- **`async_step_user`**: zeigt leeres Formular an (keine Nutzereingaben nötig)
- **`async_step_wait_for_device`**: startet Discovery-Task, zeigt Fortschrittsbalken
- **`_async_wait_for_device`**: führt `searchDevices` aus, wartet bis zu 5 Sekunden auf ein Gerät
- **`async_step_search_timeout`** / **`async_step_search_complete`**: Ergebnis-Handling
- Nur eine Config-Entry möglich (`single_config_entry: true` in manifest)

### `gateway.py` (`HausbusGateway`)
- Implementiert `IBusDataListener` und `IBusDeviceListener`
- **`async_get_home_server`**: stellt sicher, dass `HomeServer` nur einmal pro HA-Instanz erstellt wird  
  (Singleton-Problem: `HomeServer.__new__` gibt immer dieselbe Instanz zurück, aber `__init__` startet jedes Mal neue Threads)
- **`newDeviceDetected`**: registriert Gerät in der HA-Device-Registry, dispatcht Kanäle über `NEW_CHANNEL_ADDED`
- **`busDataReceived`**: leitet eingehende Nachrichten per Dispatcher an die zugehörige Entity weiter  
  (`"hausbus_update_{objectId}"`)
- Verfolgt bereits registrierte Kanäle in `registered_channels: set[int]` (verhindert Duplikate)

### `entity.py` (`HausbusEntity`)
- Basisklasse für alle haus-bus.de Entities
- `_attr_has_entity_name = True`, `_attr_should_poll = False`
- `unique_id`: `"{deviceId}-{kanaltyp}-{instanceId}"` (z.B. `"100-rollladen-1"`)
- **`async_added_to_hass`**: registriert Dispatcher-Listener für `"hausbus_update_{objectId}"`  
  und fragt sofort Hardware-Status an (`getStatus`, `getConfiguration`)
- Cleanup via `self.async_on_remove(...)` – symmetrisch zu `async_added_to_hass`

### `cover.py` (`HausbusCover`)
- Erbt von `HausbusEntity` und `CoverEntity`
- `PARALLEL_UPDATES = 0` (UDP-Sends sind fire-and-forget, kein Limit nötig)
- **Positionskonvention**: haus-bus.de definiert `0 = offen`, `100 = geschlossen`  
  Home Assistant definiert `0 = geschlossen`, `100 = offen`  
  → Umrechnung: `ha_position = 100 - bus_position`
- Unterstützte Features: `OPEN`, `CLOSE`, `STOP`, `SET_POSITION`
- Behandelte Ereignisse:
  - `EvStart` → `is_opening` / `is_closing` setzen
  - `EvClosed` → Position aus `data.getPosition()` (invertiert)
  - `EvOpen` → Position = 100
  - `Status` → aktuelle Position (invertiert)
  - `Configuration` → gespeichert in `_configuration`

---

## pyhausbus-Bibliothek: Wichtige Klassen

| Klasse | Beschreibung |
|--------|-------------|
| `HomeServer` | Singleton; koordiniert Entdeckung, hält Caches für `ModuleId`, `Configuration`, `RemoteObjects` |
| `BusHandler` | Singleton; UDP-Socket, sendet/empfängt, benachrichtigt Listener |
| `ABusFeature` | Basisklasse aller Kanäle; hat `objectId`, `name`, `getStatus()`, `getConfiguration()` |
| `ObjectId` | Hilfsklasse zur Dekodierung von 32-Bit-Adressen |
| `Rollladen(ABusFeature)` | Cover-Kanal; Methoden: `start(EDirection)`, `stop()`, `moveToPosition(int)`, `getStatus()`, `getConfiguration()` |
| `DeviceWorker` | Hintergrundthread; holt Konfiguration + RemoteObjects für jedes entdeckte Gerät |
| `DeviceCollector` | Hintergrundthread; sammelt Geräteantworten, leitet nach 0.5s Timeout an DeviceWorker |
| `IBusDeviceListener` | Interface: `newDeviceDetected(device_id, model_type, module_id, configuration, channels)` |
| `IBusDataListener` | Interface: `busDataReceived(BusDataMessage)` |

### `Rollladen`-API (für Cover-Steuerung)
```python
rollladen.start(EDirection.TO_OPEN)    # Cover öffnen
rollladen.start(EDirection.TO_CLOSE)   # Cover schließen
rollladen.stop()                        # Cover stoppen
rollladen.moveToPosition(pos)          # pos: 0=offen, 100=geschlossen (haus-bus.de Konvention)
rollladen.getStatus()                   # Status anfragen → Antwort kommt als Status-Objekt per Dispatcher
rollladen.getConfiguration()            # Konfiguration anfragen → Antwort kommt als Configuration-Objekt
```

### Empfangene Ereignisse (Rollladen)
| Klasse | Bedeutung |
|--------|-----------|
| `EvStart(direction)` | Bewegung gestartet; `direction.getDirection()` → `EDirection.TO_OPEN` / `TO_CLOSE` |
| `EvClosed(position)` | Endstellung erreicht; `position` = 100 wenn vollständig geschlossen |
| `EvOpen()` | Endstellung offen erreicht |
| `Status(position)` | Aktuelle Position; `0` = offen, `100` = geschlossen |
| `Configuration` | Konfigurationsdaten (closeTime, openTime, options) |

---

## Qualitätsstufe (Bronze)

### Bronze: vollständig implementiert
- `brands`, `common-modules`, `config-flow`, `dependency-transparency`
- `entity-event-setup`, `entity-unique-id`, `has-entity-name`, `runtime-data`
- `test-before-configure`, `test-before-setup`, `unique-config-entry`
- `config-flow-test-coverage`, `parallel-updates`

### Bronze: exempt (nicht anwendbar)
- `action-setup`, `appropriate-polling`, `docs-actions` (kein Polling, keine Actions)

### Silver/Gold/Platinum: noch `todo`
- `config-entry-unloading`, `entity-unavailable`, `log-when-unavailable`
- `test-coverage`, `devices`, `diagnostics`, `dynamic-devices`
- `entity-translations`, `exception-translations`, `icon-translations`
- `stale-devices`, `strict-typing`, u.a.

---

## Tests

Testdateien unter `tests/components/hausbus/`:

- **`conftest.py`**: `mock_home_server`-Fixture – patcht `HomeServer` in `gateway.py` (verhindert echte UDP-Sockets)
- **`test_config_flow.py`**: Config-Flow-Szenarien (Gerät gefunden, Timeout, Retry, Single-Entry)
- **`test_cover.py`**: Cover-Platform-Tests; simuliert Discovery mit echtem Gateway-Pfad, testet alle Dispatcher-Ereignisse und Service-Calls
- **`test_gateway.py`**: Gateway-Tests
- **`test_init.py`**: Setup/Unload-Tests

### Wichtige Konstanten in Tests
```python
DEVICE_ID = 100
INSTANCE_ID = 1
OBJECT_ID = HausBusUtils.getObjectId(DEVICE_ID, Rollladen.CLASS_ID, INSTANCE_ID)
UNIQUE_ID = f"{DEVICE_ID}-rollladen-{INSTANCE_ID}"
UPDATE_SIGNAL = f"hausbus_update_{OBJECT_ID}"
```

---

## Entwicklungshinweise

### Neue Plattformen hinzufügen
1. Neues Plattformmodul anlegen (z.B. `light.py`, `switch.py`)
2. In `PLATFORMS`-Liste in `__init__.py` eintragen
3. In `cover.py` als Beispiel für Event-Handling und Dispatcher-Nutzung orientieren
4. Kanal-Klasse aus `pyhausbus.de.hausbus.homeassistant.proxy.*` importieren
5. In `_handle_channel_added` auf den neuen Kanaltyp prüfen (`isinstance(channel, NewClass)`)

### Position-Konvention beachten
**haus-bus.de**: `0 = offen`, `100 = geschlossen`  
**Home Assistant**: `0 = geschlossen`, `100 = offen`  
Immer invertieren: `ha_pos = 100 - bus_pos`

### Thread-Sicherheit
- `newDeviceDetected` und `busDataReceived` werden in Hintergrundthreads aufgerufen
- Für HA-Loop-Calls immer `hass.loop.call_soon_threadsafe(...)` oder `asyncio.run_coroutine_threadsafe(...)` verwenden
- Entity-Callbacks müssen `@callback` haben (sonst führt der Dispatcher sie im Executor aus)

### HomeServer-Singleton-Problem
`HomeServer.__new__` gibt immer die gleiche Instanz zurück, aber `HomeServer.__init__` startet jedes Mal neue Hintergrundthreads. Deshalb wird `HomeServer` nur einmal pro HA-Instanz in `async_get_home_server` erzeugt (gespeichert in `hass.data[DOMAIN]["home_server"]`).

---

## manifest.json

```json
{
  "domain": "hausbus",
  "name": "Haus-Bus",
  "codeowners": ["@hausbus"],
  "config_flow": true,
  "documentation": "https://www.home-assistant.io/integrations/hausbus",
  "iot_class": "local_push",
  "loggers": ["pyhausbus"],
  "quality_scale": "bronze",
  "requirements": ["pyhausbus==1.0.52"],
  "single_config_entry": true
}
```

---

## Abhängigkeiten

| Paket | Version | Zweck |
|-------|---------|-------|
| `pyhausbus` | `1.0.52` | Python-Bibliothek für haus-bus.de Kommunikation |

Lokale Entwicklungsquelle der Bibliothek: `D:\code\hacore\PyHausBus-main\`
