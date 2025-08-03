#!/bin/bash
# Installation Script für Green Planet Energy Integration

echo "📦 Installiere Green Planet Energy Integration..."

# Custom Components Ordner erstellen
mkdir -p config/custom_components/green_planet_energy

# Integration kopieren (aus dem aktualisierten homeassistant/components Ordner)
echo "📋 Kopiere Dateien..."
cp -r homeassistant/components/green_planet_energy/* config/custom_components/green_planet_energy/

echo "✅ Installation abgeschlossen!"
echo ""
echo "🔄 Nächste Schritte:"
echo "1. Home Assistant neustarten"
echo "2. Einstellungen → Geräte & Dienste → Integration hinzufügen"
echo "3. 'Green Planet Energy' suchen und hinzufügen"
echo ""
echo "📊 Nach der Installation sind folgende Sensoren verfügbar:"
echo "   - 24 Stunden-Sensoren: sensor.preis_00_00 bis sensor.preis_23_00"
echo "   - Höchster Preis heute: sensor.green_planet_energy_..._highest_price_today"
echo "   - Niedrigster Preis heute: sensor.green_planet_energy_..._lowest_price_today"
echo "   - Aktueller Preis: sensor.green_planet_energy_..._current_price"
