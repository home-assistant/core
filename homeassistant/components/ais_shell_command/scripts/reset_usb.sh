for X in /sys/bus/usb/devices/*; do
    $(su -c "log -p i 'AIS-dom $X'")
    if [ -f "$X/idVendor" ]
    then
    	idVendor=$(cat "$X/idVendor")  || idVendor=""
    	idProduct=$(cat "$X/idProduct") || idProduct=""
    	if [ $idVendor == "0c45" ] && [ $idProduct == "5102" ]
    	then
    		$(su -c "log -p i 'reset_usb resetUsb device idVendor $idVendor idProduct $idProduct'")
        	command="echo 0 > $X/authorized"
        	$(su -c "$command")
        	command="echo 1 > $X/authorized"
        	$(su -c "$command")
        	$(su -c "log -p i 'AIS-dom reset_usb resetUsb -> $command'")
    	fi
     fi
done
