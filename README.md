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
- Načítání profilových hodnot z `https://data.distribuce24.cz/rest/spotreby`.
- Senzor poslední platné naměřené hodnoty.
- Senzor energie za nastavené období; pro typ měření C1 se používá samostatný endpoint `/openApi/spotreby`, u výkonových A/B profilů (`ICC1`/`ISC1`) se čtvrthodinové kW hodnoty přepočítají na kWh dělením 4.
- Podpora běžných profilů EG.D, například:
  - `ICC1` – činná spotřeba ze sítě jako čtvrthodinový výkon v kW,
  - `ICQ2` – činná spotřeba ze sítě v kWh,
  - `ISC1` – činná dodávka/přetok do sítě jako čtvrthodinový výkon v kW,
  - `ISQ2` – činná dodávka/přetok do sítě v kWh.

## Typ měření a profil

Novější návod EG.D rozlišuje dvě větve API:

| Typ měření | Co zadat do pole Profil | Endpoint | Poznámka |
| --- | --- | --- | --- |
| **C1** spotřeba celkem | `0.0.2.4.1.2.12.0.0.0.0.0.0.0.0.3.72.0` | `/openApi/spotreby` | výchozí volba pro C1, kWh |
| **C1** dodávka celkem | `0.0.2.4.19.2.12.0.0.0.0.0.0.0.0.3.72.0` | `/openApi/spotreby` | přetok/dodávka, kWh |
| **C1** spotřeba VT | `0.0.2.4.1.2.12.0.0.0.0.2.0.0.0.3.72.0` | `/openApi/spotreby` | vysoký tarif, kWh |
| **C1** spotřeba NT | `0.0.2.4.1.2.12.0.0.0.0.3.0.0.0.3.72.0` | `/openApi/spotreby` | nízký tarif, kWh |
| **A/B** spotřeba výkon | `ICC1` | `/rest/spotreby` | čtvrthodinový výkon v kW |
| **A/B** spotřeba energie | `ICQ2` | `/rest/spotreby` | energie v kWh, podle dokumentace od 1. 7. 2024 |
| **A/B** dodávka výkon | `ISC1` | `/rest/spotreby` | čtvrthodinový výkon v kW |
| **A/B** dodávka energie | `ISQ2` | `/rest/spotreby` | energie v kWh, podle dokumentace od 1. 7. 2024 |

Pokud máte chytré měření **C1**, nepoužívejte `ICC1`; do pole **Profil** zadejte dlouhý C1 kód z číselníku. Integrace potom zavolá `/openApi/spotreby` a předá tento kód v parametru `profile`. Profily `ICC1`, `ICQ2`, `ISC1`, `ISQ2` zůstávají pro starší větev měření A/B přes `/rest/spotreby`.

## Konfigurace

V portálu Distribuce24 / EG.D si v části vzdáleného přístupu OpenAPI vygenerujte:

- `client_id`,
- `client_secret`,
- EAN/EIC odběrného místa,
- typ/profil: pro chytré měření C1 zadejte dlouhý C1 kód, například `0.0.2.4.1.2.12.0.0.0.0.0.0.0.0.3.72.0`; pro A/B zadejte profil například `ICC1`, `ICQ2`, `ISC1` nebo `ISQ2`.

Integrace data načítá jednou denně, protože EG.D měřená data aktualizuje denně a dokumentace varuje před zbytečně častým voláním API. Rozsah dotazu vždy končí nejpozději včera ve 23:45 v časové zóně Europe/Prague a do API se posílá přepočtený UTC čas, protože EG.D odmítá hodnoty `from`/`to` zasahující do dnešního lokálního dne.

## Řešení problémů

Pokud se při přidání integrace zobrazí `cannot_connect`, integrace při ověření kontroluje pouze platnost `client_id` / `client_secret` a dostupnost API číselníku statusů. Nevyžaduje už existující měřená data za poslední dny, protože ta mohou být u správně nastaveného odběrného místa dočasně prázdná.

Zkontrolujte hlavně:

- že používáte `client_id` a `client_secret` pro vzdálený přístup OpenAPI,
- že v EG.D / Distribuce24 portálu je vzdálený přístup aktivní,
- že Home Assistant má přístup na `https://idm.distribuce24.cz` a `https://data.distribuce24.cz`,
- že profil odpovídá tomu, co vám API pro dané odběrné místo vrací; pro typ měření C1 zadejte dlouhý C1 kód z číselníku, ne `ICC1`,
- že používáte verzi integrace s opravou časové zóny, která neposílá v letním čase `to` jako 23:45 UTC, protože to u EG.D může spadnout do dnešního lokálního dne.
