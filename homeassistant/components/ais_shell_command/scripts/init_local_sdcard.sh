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

if [ ! -e "/sdcard/dom" ] ; then
    mkdir -p /sdcard/dom
    mkdir -p /sdcard/dom/Książki
    mkdir -p /sdcard/dom/Muzyka
    mkdir -p /sdcard/dom/Hasła
fi

if [ ! -e "/sdcard/dom/informacja.txt" ] ; then
    touch "/sdcard/dom/informacja.txt"
    echo "Cześć, przeglądasz folder w lokalizacji dostępnej dla wszystkich aplikacji, ta lokalizacja to /sdcard/dom" > /sdcard/dom/informacja.txt
    echo "folder ten jest dostępny w twojej lokalnej sieci (protokół ftp) pod adresem ftp://ais-dom:1024/sdcard/dom" >> /sdcard/dom/informacja.txt
    echo "możesz tu dodać muzykę lub pliki tekstowe a następnie je odtwarzać w aplikacji" >> /sdcard/dom/informacja.txt
    echo "w przyszłości będziemy synchronizować pliki w tej lokalizacji z Google Drive " >> /sdcard/dom/informacja.txt
    echo "Pozdrowienia, Twój Asystent domowy!" >> /sdcard/dom/informacja.txt
    echo "PS w tej pierwszej wersji, odsługujemy tylko mp3 i txt, oczywiście to się w przyszłości rozwinie. Koniec wiadomości." >> /sdcard/dom/informacja.txt
fi



