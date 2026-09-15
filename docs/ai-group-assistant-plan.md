# Plan: jawny AI assistant dla grup Telegram

Status: plan defensywny, do przeglądu przez właściciela systemu,
bezpieczeństwa i prywatności. Dokument jest dopasowany do Home Assistant Core:
ewentualna implementacja musi respektować istniejące wzorce config entry,
service/action schemas, logowanie i politykę AI repozytorium. Ten plik sam w
sobie nie dodaje integracji, kodu produkcyjnego ani zależności.

## Cel

Asystent ma odpowiadać w wyraźnie oznaczonym koncie Telegram i pomagać grupie
wykonywać bezpieczne, odwracalne operacje Home Assistant. Użytkownik zawsze
wie, że rozmawia z automatyzacją: nazwa, avatar, komunikat powitalny i każda
odpowiedź wskazują „AI assistant”. Konto nie podszywa się pod człowieka.

Zakres pierwszej wersji jest wąski: odczyt stanu zatwierdzonych encji,
wyjaśnienie zdarzenia oraz przygotowanie propozycji akcji. Akcja zmieniająca
stan (np. światło lub scenę) wymaga jawnego potwierdzenia człowieka w tej samej
rozmowie; operacje administracyjne, zamki, alarmy, dostęp do sekretów i
zmiany konfiguracji są domyślnie wyłączone.

## Model integracji i uprawnień

Warstwa Telegram/Telethon działa jako osobny proces/adapter, a komunikacja z
Home Assistant używa ograniczonego tokenu i istniejącego, jawnego interfejsu
usług. Token nie ma uprawnień administratora. Lista dozwolonych grup,
użytkowników, encji, domen i usług jest allowlistą przechowywaną w konfiguracji
integracji; denylist nie jest mechanizmem bezpieczeństwa.

Minimalny zakres:

- konto bota i `api_id`/`api_hash` Telethon są w menedżerze sekretów, nigdy w
  repozytorium, logu, promptach ani kopii wiadomości;
- bot może czytać wyłącznie wiadomości w zatwierdzonych grupach i reagować
  tylko na jawne polecenia lub wzmianki; DM-y, nowe grupy i forwardy są
  odrzucane do czasu ręcznej akceptacji;
- token Home Assistant jest ograniczony do konkretnych encji/usług
  odczytowych i zatwierdzonych akcji. Brak dostępu do plików, panelu
  administracyjnego, add-onów, terminala i arbitralnego wywoływania usług;
- wyjście modelu jest nieufne: parser dopuszcza tylko schemat typowany,
  sprawdza encję, usługę, parametry, zakres i aktualny stan, a błędne dane
  kończą się jawnym odrzuceniem;
- limit częstotliwości, limit kosztu i circuit breaker zatrzymują automatyczne
  odpowiedzi przy pętli, błędach API lub anomalii.

## Human-in-the-loop

Asystent najpierw pokazuje plan: aktora, grupę, encję, usługę, parametry,
przewidywany skutek i czas wygaśnięcia. Wykonanie wymaga potwierdzenia
uprawnionego człowieka przyciskiem lub jednoznaczną komendą, z korelacją do
konkretnej propozycji. „Tak” z innej wiadomości, cytatu lub niezweryfikowanego
forwardu nie wystarcza. Potwierdzenie wygasa po krótkim czasie i po zmianie
stanu; akcje nieodwracalne wymagają dodatkowego potwierdzenia albo są
niedostępne.

Każde wykonanie zwraca wynik, a niepowodzenie jest widoczne dla grupy i
operatora. Operator może wstrzymać bota, unieważnić token i przejrzeć audyt
bez dostępu do hosta przez niejawny kanał.

## Prywatność, retencja i logi

Do modelu trafia minimalny kontekst: identyfikator dozwolonej encji, stan
potrzebny do odpowiedzi i wiadomość po usunięciu niepotrzebnych danych
osobowych. Nie wysyłać historii grupy, sekretów, tokenów, lokalizacji ani
pełnych logów, jeśli nie są wymagane. Dostawca modelu musi mieć zatwierdzoną
umowę i politykę braku trenowania na danych organizacji; awaria dostawcy nie
może odblokować szerszych uprawnień.

Retencja jest jawna i konfigurowalna: treść wiadomości i prompt/response
przechowywać tylko przez minimalny okres operacyjny, metadane akcji i audyt
dłużej zgodnie z polityką bezpieczeństwa, a kopie zapasowe zgodnie z ich
retencją. Usunięcie po terminie jest weryfikowalne i audytowane; nie ma
self-erasure ani kasowania dowodów na żądanie bota. Użytkownik grupy otrzymuje
informację o retencji i sposobie żądania usunięcia danych.

Centralne logowanie obejmuje: correlation ID, Telegram chat/user ID w formie
ograniczonej lub pseudonimizowanej, wybraną intencję, walidację, decyzję
człowieka, wywołaną usługę, wynik, opóźnienie i wersję polityki/modelu.
Nie logować tokenów, pełnych sekretów ani niepotrzebnej treści rozmów.

## Obsługa incydentów i recovery

Alerty obejmują próbę użycia spoza allowlisty, prompt injection, nietypową
liczbę żądań, zmianę uprawnień, odrzucenie schematu i rozjazd konfiguracji.
Runbook: zatrzymać adapter, unieważnić tokeny Telegram/Home Assistant,
zachować centralny audyt, zablokować akcje zmieniające stan, poinformować
operatora i odtworzyć konfigurację z podpisanej kopii. Po incydencie wykonać
test negatywny (brak dostępu do sekretów i usług) oraz ponowną akceptację
człowieka. Recovery nie uruchamia samodzielnie zaległych poleceń.

## Testy i wdrożenie

Przed stagingiem wymagane są testy: allowlista grup i encji, brak tokenów w
logach, odrzucenie prompt injection i forwardów, wygasanie potwierdzeń,
idempotencja i limit żądań, awaria Telethon/modelu, centralne logowanie,
retencja oraz zatrzymanie obwodem bezpieczeństwa. Testy integracyjne powinny
używać atrap Telegram/Telethon i Home Assistant, bez prawdziwych sekretów.
Wdrożenie etapowe: dry-run, grupa testowa, przegląd audytu, dopiero potem
ograniczona produkcja. Każda zmiana promptu, modelu, allowlisty lub uprawnień
wymaga przeglądu i wersjonowania.

## Jawne wykluczenia

Projekt **nie** zawiera C2, evasion, ukrytego zarządzania/persistence,
reverse shell, port knocking, eksfiltracji, **Shadow Agent** ani self-erasure.
Bot nie ukrywa swojej tożsamości, nie tworzy kanałów obejścia, nie utrwala się
poza zatwierdzonym wdrożeniem, nie wysyła danych poza dozwolony zakres i nie
usuwa logów ani własnych śladów. Telegram/Telethon jest kanałem jawnej
interakcji, nie kanałem dowodzenia dla arbitralnego kodu.

## Kryteria akceptacji

Właściciel musi zatwierdzić diagram przepływu danych, allowlistę, zakres
tokenu, retencję, dostawcę modelu, procedurę IR i plan wycofania. Gotowość
oznacza przejście testów negatywnych, widoczny komunikat „AI assistant”,
udokumentowane potwierdzenie człowieka i możliwość natychmiastowego
unieważnienia wszystkich poświadczeń.
