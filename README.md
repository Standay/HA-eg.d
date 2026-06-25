# EG.D Distribution pro Home Assistant

Custom integrace pro načítání profilových dat spotřeby/dodávky elektřiny z EG.D / Distribuce24 OpenAPI.

## Nejjednodušší instalace přes HACS

Tento repozitář je připravený jako **HACS custom repository**, takže není potřeba ručně kopírovat složku `custom_components`.

1. V Home Assistant otevřete **HACS → Integrations**.
2. Vpravo nahoře klikněte na **⋮ → Custom repositories**.
3. Do pole **Repository** vložte URL tohoto GitHub repozitáře.
4. V poli **Category** vyberte **Integration**.
5. Klikněte na **Add**.
6. Vyhledejte **EG.D Distribution** a klikněte na **Download**.
7. Restartujte Home Assistant.
8. Přidejte integraci přes **Settings → Devices & services → Add integration → EG.D Distribution**.

> Pokud HACS ještě nemáte, nainstalujte jej podle oficiální dokumentace HACS. Po instalaci HACS už další aktualizace této integrace půjdou provádět přímo z UI Home Assistantu.

## Ruční instalace, jen pokud nechcete HACS

Zkopírujte složku `custom_components/egd_distribution` do složky `custom_components` ve vaší konfiguraci Home Assistantu a restartujte Home Assistant.

## Co integrace umí

- OAuth2 `client_credentials` autentizace proti `https://idm.distribuce24.cz/oauth/token`.
- Načítání profilových hodnot z produkčního API `https://data.distribuce24.cz/rest`.
- Senzor posledního platného 15min intervalu, součtu za načtené období, včerejší energie, času posledních dat a pokrytí dat.
- Import hodinových součtů do Home Assistant long-term statistics pro Energy dashboard. Běžná C1 spotřeba funguje přes profil `DCQC` na endpointu `/spotreby`, dlouhé C1 kódy používají samostatnou `/c/spotreby` větev a u výkonových A/B profilů (`ICC1`/`ISC1`) se čtvrthodinové kW hodnoty přepočítají na kWh dělením 4.
- Podpora běžných profilů EG.D, například:
  - `ICC1` – činná spotřeba ze sítě jako čtvrthodinový výkon v kW,
  - `ICQ2` – činná spotřeba ze sítě v kWh,
  - `ISC1` – činná dodávka/přetok do sítě jako čtvrthodinový výkon v kW,
  - `ISQ2` – činná dodávka/přetok do sítě v kWh.

## Typ měření a profil

Novější návod EG.D rozlišuje dvě větve API:

| Typ měření | Co zadat do pole Profil | Zdroj dat | Endpoint | Poznámka |
| --- | --- | --- | --- | --- |
| **C1** spotřeba odebraná ze sítě | `DCQC` | - | `/rest/spotreby` | ověřená produkční cesta pro C1, kWh |
| **C1** spotřeba celkem přes /c větev | `0.0.2.4.1.2.12.0.0.0.0.0.0.0.0.3.72.0` | `ODBERNE_MISTO` | `/rest/c/spotreby` | dlouhý kód z číselníku |
| **C1** dodávka celkem | `0.0.2.4.19.2.12.0.0.0.0.0.0.0.0.3.72.0` | `ODBERNE_MISTO` | `/rest/c/spotreby` | přetok/dodávka, kWh |
| **C1** spotřeba z elektroměru | `0.0.2.4.1.2.12.0.0.0.0.0.0.0.0.3.72.0` | `ELEKTROMER` | `/rest/c/spotreby` | stejný kód jako celkem, jiný zdroj dat |
| **C1** dodávka z elektroměru | `0.0.2.4.19.2.12.0.0.0.0.0.0.0.0.3.72.0` | `ELEKTROMER` | `/rest/c/spotreby` | stejný kód jako celkem, jiný zdroj dat |
| **C1** spotřeba VT | `0.0.2.4.1.2.12.0.0.0.0.2.0.0.0.3.72.0` | `ELEKTROMER` | `/rest/c/spotreby` | vysoký tarif, kWh |
| **C1** spotřeba NT | `0.0.2.4.1.2.12.0.0.0.0.3.0.0.0.3.72.0` | `ELEKTROMER` | `/rest/c/spotreby` | nízký tarif, kWh |
| **A/B** spotřeba výkon | `ICC1` | - | `/rest/spotreby` | čtvrthodinový výkon v kW |
| **A/B** spotřeba energie | `ICQ2` | - | `/rest/spotreby` | energie v kWh, podle dokumentace od 1. 7. 2024 |
| **A/B** dodávka výkon | `ISC1` | - | `/rest/spotreby` | čtvrthodinový výkon v kW |
| **A/B** dodávka energie | `ISQ2` | - | `/rest/spotreby` | energie v kWh, podle dokumentace od 1. 7. 2024 |

Pokud máte chytré měření **C1** a chcete běžnou spotřebu v kWh, začněte profilem `DCQC`. Živý produkční test ukázal, že `DCQC` se pro C1 vrací v číselníku `/rest/profily` a funguje přes `/rest/spotreby`. Dlouhé C1 kódy integrace stále podporuje přes `/rest/c/spotreby`, ale používejte je až ve chvíli, kdy víte, že je pro vaše odběrné místo tato větev API oprávněná. Profily `ICC1`, `ICQ2`, `ISC1`, `ISQ2` zůstávají pro větev měření A/B přes `/rest/spotreby`.

## Konfigurace

V portálu Distribuce24 / EG.D si v části vzdáleného přístupu OpenAPI vygenerujte:

- `client_id`,
- `client_secret`,
- EAN/EIC odběrného místa,
- typ/profil: pro chytré měření C1 spotřeby začněte profilem `DCQC`; pro A/B zadejte profil například `ICC1`, `ICQ2`, `ISC1` nebo `ISQ2`; dlouhé C1 kódy z číselníku používejte jen pro `/c` větev,
- zdroj dat pro C1: vyplňuje se jen pro dlouhé C1 kódy; podle číselníku dokumentace `ODBERNE_MISTO` pro hodnoty odběrného místa nebo `ELEKTROMER` pro hodnoty elektroměru, tarify a stavy číselníků.

Integrace data načítá jednou denně, protože EG.D měřená data aktualizuje denně a dokumentace varuje před zbytečně častým voláním API. Rozsah dotazu vždy končí nejpozději včera ve 23:45 v časové zóně Europe/Prague a do API se posílá přepočtený UTC čas, protože EG.D odmítá hodnoty `from`/`to` zasahující do dnešního lokálního dne.

Profil, zdroj dat, počet dnů k načtení a endpointy lze později změnit přes **Settings → Devices & services → EG.D Distribution → Configure**. Není nutné integraci mazat a znovu zadávat `client_id`, `client_secret` a EAN.

## Senzory a Energy dashboard

Integrace rozlišuje běžné zobrazovací senzory od dlouhodobých statistik:

- **Latest interval energy / average power** ukazuje poslední platný 15min interval z EG.D. Není to živá okamžitá spotřeba.
- **Fetched period energy** je součet validních hodnot za načtené okno. Hodí se na kontrolu a přehled, ale není označený jako dlouhodobý čítač, protože se rolling okno může při dalším načtení snížit.
- **Yesterday energy** je součet za poslední kompletní lokální den vrácený API.
- **Last data timestamp** a **Data coverage** jsou diagnostické senzory pro kontrolu stáří a úplnosti dat.

Pro Energy dashboard integrace z validních 15min hodnot vytváří hodinové externí statistiky v kWh. Při každém úspěšném načtení znovu porovná celé nastavené okno s recorder statistikami a doplní nebo opraví chybějící hodiny. Pokud později zvýšíte **Počet dnů k načtení** například na `31`, integrace při dalším načtení dotáhne starší dostupná data bez mazání integrace.

Pro testovací přístup podle dokumentace změňte **Token URL** na `https://test.distribuce24.cz/idm/oauth/token` a **API URL** na `https://test.distribuce24.cz/openApi`. Ověřený testovací přístup pro EAN `859182400100004000` vrací data přes `/spotreby`; použijte například profil `ICQ2` pro spotřebu v kWh, `ICC1` pro čtvrthodinový výkon v kW nebo `DCQC` pro C1-like spotřebu v kWh. Testovací portál u tohoto přístupu vrací u validních hodnot status `W` a endpointy `/c/statusy`, `/c/profily`, `/c/spotreby` odpovídají `Není dostupné na testovacím portálu`.

## Řešení problémů

Pokud se při přidání integrace zobrazí `cannot_connect`, integrace při ověření kontroluje získání OAuth tokenu z `client_id` / `client_secret`. Nevyžaduje už existující měřená data za poslední dny, protože ta mohou být u správně nastaveného odběrného místa dočasně prázdná.

Zkontrolujte hlavně:

- že používáte `client_id` a `client_secret` pro vzdálený přístup OpenAPI,
- že v EG.D / Distribuce24 portálu je vzdálený přístup aktivní,
- že Home Assistant má přístup na `https://idm.distribuce24.cz` a `https://data.distribuce24.cz`,
- že profil odpovídá tomu, co vám API pro dané odběrné místo vrací; pro běžnou C1 spotřebu zkuste nejdřív `DCQC`, ne `ICC1`,
- že používáte verzi integrace s opravou časové zóny, která neposílá v letním čase `to` jako 23:45 UTC, protože to u EG.D může spadnout do dnešního lokálního dne.

Pokud EG.D vrátí `validation_error` s textem `V požadovaném období nemáte oprávnění na data odběrného místa`, integrace zkusí místo nastaveného vícedenního okna ještě samotný včerejšek. Pokud EG.D odmítne i ten, nastavení integrace už nespadne do nekonečného retry; senzory zůstanou bez hodnoty a poslední chyba bude v jejich atributech.

Živé testovací odpovědi ukazují, že `total` v odpovědi `/spotreby` odpovídá počtu položek vrácených na aktuální stránce, ne celkovému počtu všech záznamů. Integrace proto stránkuje podle `PageStart`/`PageSize` a končí až ve chvíli, kdy stránka vrátí méně položek než požadovaný `PageSize`.
