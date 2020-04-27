#!/data/data/pl.sviete.dom/files/usr/bin/sh

micVendor="0c45"
micProduct="5102"

for X in /sys/bus/usb/devices/*; do
    if [ -f "$X/idVendor" ]
    then
    	idVendor=$(cat "$X/idVendor")  || idVendor=""
    	idProduct=$(cat "$X/idProduct") || idProduct=""
    	if [ "$idVendor" = "$micVendor" ]; then
		    if [ "$idProduct" = "$micProduct" ]; then
        		command="echo 0 > $X/authorized"
        		command="echo 1 > $X/authorized"
        		$(su -c "log -p i 'reset_usb resetUsb device idVendor $idVendor idProduct $idProduct'")
    			  return 0
		    fi
	    fi
     fi
done
return 0