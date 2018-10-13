#!/data/data/pl.sviete.dom/files/usr/bin/sh

set -e -u

SCRIPTNAME=init_local
show_usage() {
    echo "Usage: $SCRIPTNAME"
    echo "Set the structure for the local files on sdcard folder"
}

if [ $# != 0 ]; then
    show_usage
fi

# to fix the problems with permissions to rclone config
su -c "chmod -R 777 /sdcard/rclone"

if [ ! -e "/sdcard/dom" ] ; then
    mkdir -p /sdcard/dom
    mkdir -p /sdcard/dom/Książki
    mkdir -p /sdcard/dom/Muzyka
    mkdir -p /sdcard/dom/Hasła
fi

if [ ! -e "/sdcard/dom/informacja.txt" ] ; then
    touch "/sdcard/dom/informacja.txt"
    echo "Cześć, przeglądasz dyski w systemie. Obsługujemy trzy rodzaje dysków:" > /sdcard/dom/informacja.txt
    echo "1. 'Dysk-wewnętrzny' jest to folder w pamięci urządzenia umieszczony w lokalizacji dostępnej dla wszystkich aplikacji, ta lokalizacja to /sdcard/dom "
    echo "folder ten jest dostępny w twojej lokalnej sieci (protokół ftp) pod adresem ftp://ais-dom:1024/sdcard/dom" >> /sdcard/dom/informacja.txt
    echo "możesz tu dodać muzykę lub pliki tekstowe a następnie je odtwarzać w aplikacji." >> /sdcard/dom/informacja.txt
    echo "2. 'Dyski-zewnętrzne' są to dołączone do urządzenia karty SD lub pamięciu USB " >> /sdcard/dom/informacja.txt
    echo "3. 'Dyski-zdalne' są to dyski/usługi przechowywania danych w churach. Połączenie z dyskami zdalnymi definiowane jest w ustawieniach aplikacji. " >> /sdcard/dom/informacja.txt
    echo "Pozdrowienia, Twój Asystent domowy!" >> /sdcard/dom/informacja.txt
    echo "PS Obecnie odtwarzamy pliki tekstowe i pliki audio. Koniec wiadomości." >> /sdcard/dom/informacja.txt
fi



