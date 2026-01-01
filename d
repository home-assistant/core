diff --git a/homeassistant/components/velbus/light.py b/homeassistant/components/velbus/light.py
index df530e2081f..b2bcb50421f 100644
--- a/homeassistant/components/velbus/light.py
+++ b/homeassistant/components/velbus/light.py
@@ -78,9 +78,7 @@ class VelbusLight(VelbusEntity, LightEntity):
             if kwargs[ATTR_BRIGHTNESS] == 0:
                 brightness = 0
             else:
-                brightness = math.floor(
-                    brightness_to_value(BRIGHTNESS_SCALE, kwargs[ATTR_BRIGHTNESS])
-                )
+                brightness = max(1, int(brightness_to_value(BRIGHTNESS_SCALE, kwargs[ATTR_BRIGHTNESS])))
             attr, *args = (
                 "set_dimmer_state",
                 brightness,
