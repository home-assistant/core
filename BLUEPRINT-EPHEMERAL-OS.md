# Blueprint: defensywny, ephemeralny system operacyjny

Status: propozycja architektoniczna i operacyjna. Dokument nie zmienia kodu
Home Assistant ani jego zależności. Ma służyć jako punkt odniesienia dla
wdrożeń, obrazów systemu i procedur utrzymaniowych.

## Cel i granice

Blueprint opisuje hosta uruchamiającego Home Assistant w możliwie krótkotrwałym
środowisku: system jest budowany z reprodukowalnego obrazu, uruchamiany z
minimalnym stanem lokalnym i odtwarzany zamiast „naprawiany” na miejscu.
Konfiguracja użytkownika, kopie zapasowe i dane objęte retencją pozostają w
kontrolowanym, szyfrowanym magazynie; ephemeralność nie oznacza utraty danych
ani braku audytu.

Założenia:

- tylko sprzęt i firmware z włączonym **Secure Boot**; klucze platformy i klucze
  podpisywania obrazu są rozdzielone, rotowane i przechowywane poza hostem;
- **measured boot** zapisuje pomiary firmware, bootloadera, kernela, initramfsu
  i obrazu do TPM; odmienne pomiary blokują automatyczne dopuszczenie hosta;
- **TPM attestation** jest sprawdzana przez niezależny verifier przed wydaniem
  poświadczeń do usług. Attestation potwierdza stan rozruchu, ale nie zastępuje
  kontroli integralności systemu plików ani autoryzacji;
- Home Assistant działa jako nieuprzywilejowany użytkownik, z minimalnym
  zestawem capabilities, bez dostępu do urządzeń i interfejsów, których nie
  wymaga konfiguracja;
- każda zmiana obrazu, konfiguracji i polityki ma właściciela, numer wersji,
  podpis i możliwość odtworzenia poprzedniej znanej dobrej wersji.

## Warstwy zaufania i integralność

1. Firmware weryfikuje podpis bootloadera (Secure Boot).
2. Bootloader mierzy i weryfikuje kernel oraz initramfs (measured boot).
3. Initramfs sprawdza podpis obrazu root oraz politykę TPM; dysk danych jest
   szyfrowany i otwierany dopiero po udanej attestation.
4. System montuje root jako tylko do odczytu. Integralność plików obrazu jest
   weryfikowana przed startem usług i okresowo, bez automatycznego „naprawiania”
   nieznanych zmian.
5. Przy niezgodności host przechodzi do trybu recovery, nie uruchamia usług
   sterujących urządzeniami i wysyła zdarzenie do centralnego audytu.

Klucze podpisujące nie mogą być przechowywane w obrazie, w repozytorium ani na
tym samym hoście co verifier. Aktualizacja wymaga dwóch niezależnych akceptacji
dla obrazu produkcyjnego, testu na kanale staging i zachowania poprzedniego
obrazu do kontrolowanego rollbacku.

## Pamięć, procesy i sieć

- `/tmp`, `/run` i katalogi robocze są w **RAM/tmpfs**, z limitem rozmiaru,
  `nosuid`, `nodev` i (o ile kompatybilne) `noexec`; cache nie może zawierać
  sekretów po restarcie;
- swap jest wyłączony albo szyfrowany i objęty polityką wycieku danych;
- usługi mają osobne konta, ograniczone namespace'y, systemd sandboxing,
  read-only bind mounts i limit zasobów; debugowanie produkcji wymaga
  czasowego, audytowanego wyjątku;
- firewall domyślnie odrzuca ruch przychodzący. Dozwolone są wyłącznie jawnie
  opisane połączenia wychodzące do DNS/NTP, centralnego logowania, verifiera,
  wymaganych usług Home Assistant i zatwierdzonych integracji;
- administracja odbywa się przez bastion/VPN. **SSH hardening** obejmuje
  wyłącznie klucze (bez haseł i root loginu), ograniczenie użytkowników,
  MFA/bastion, krótkie sesje, rejestrowanie poleceń oraz wyłączenie
  nieużywanych forwardingów i tuneli;
- usługi i integracje nie nasłuchują na interfejsach publicznych. Tokeny są
  krótkotrwałe, zakresowe i unieważnialne; sekrety trafiają do menedżera
  sekretów, nie do logów ani obrazu.

## Logowanie, audyt i reagowanie

Logi systemowe, Secure/Measured Boot, attestation, starty usług, zmiany
konfiguracji, logowania SSH, decyzje operatorów i działania Home Assistant są
wysyłane **centralnie** po TLS z kolejką odporną na chwilową niedostępność.
Host nie może usuwać ani modyfikować potwierdzonych wpisów. Centralny system
zapewnia synchronizację czasu, kontrolę dostępu, alerty z korelacją i
niezmienny magazyn audytowy.

Minimalny audyt zawiera: czas UTC, identyfikator hosta i obrazu, aktora,
źródło, działanie, zasób, wynik, correlation ID oraz powód decyzji. Dane
osobowe i treści wiadomości są minimalizowane lub haszowane. Retencja jest
jawna: telemetria operacyjna krótka, audyt i ślady bezpieczeństwa zgodnie z
polityką organizacji i prawem; usunięcie po terminie jest samo audytowane.

Procedura IR:

1. sklasyfikować alert i zachować logi, pomiary oraz stan attestation;
2. odizolować host przez kontrolę sieci, nie kasując dowodów;
3. unieważnić tokeny i poświadczenia, zablokować automatyczne akcje;
4. porównać obraz i konfigurację z podpisaną wersją bazową;
5. odtworzyć host z czystego obrazu, przywrócić tylko zweryfikowane dane;
6. wykonać attestation, testy funkcjonalne i przegląd człowieka przed
   ponownym włączeniem automatyzacji;
7. zamknąć incydent raportem: zakres, chronologia, wpływ, poprawki i działania
   zapobiegawcze.

## Recovery i ciągłość działania

Recovery jest osobnym, podpisanym obrazem z ograniczoną siecią i bez
automatycznego wykonywania akcji w domu. Zawiera narzędzia do weryfikacji
podpisów, TPM i kopii zapasowych, ale nie zawiera kluczy produkcyjnych.
Kopie zapasowe Home Assistant są szyfrowane, wersjonowane, testowane
odtworzeniowo i przechowywane poza hostem. Ransomware lub błędna aktualizacja
nie mogą nadpisać jednocześnie hosta i kopii.

## Świadome wykluczenia

Ten blueprint **nie** opisuje ani nie dopuszcza C2, evasion, ukrytego
zarządzania/persistence, reverse shell, port knocking, eksfiltracji,
**Shadow Agent** ani self-erasure. Nie ma mechanizmu ukrywania ruchu,
samoczynnego utrwalania się, kasowania śladów ani obchodzenia zgody
operatora. Każdy kanał administracyjny jest jawny, zakresowy i audytowany.

## Kryteria akceptacji

Przed wdrożeniem należy udokumentować: wynik Secure Boot i measured boot,
udany i odrzucony przypadek TPM attestation, test integralności, limity
tmpfs/RAM, próbę nieautoryzowanego SSH, dostarczenie i niezmienność logów,
odtworzenie backupu, rollback obrazu oraz pełne ćwiczenie IR. Brak dowodu
testu oznacza brak gotowości produkcyjnej.
