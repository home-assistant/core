.PHONY: start-hass
# only here for development, not needed for production
start-hass:
#	sudo chown ${USER}:${USER} /dev/serial/by-id/usb-ITEAD_SONOFF_Zigbee_3.0_USB_Dongle_Plus_V2_20221201143303-if00;
	hass
