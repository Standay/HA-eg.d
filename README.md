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
- Senzor energie za nastavené období; u výkonových C1 profilů (`ICC1`/`ISC1`) se čtvrthodinové kW hodnoty přepočítají na kWh dělením 4.
- Podpora běžných profilů EG.D, například:
  - `ICC1` – činná spotřeba ze sítě jako čtvrthodinový výkon v kW,
  - `ICQ2` – činná spotřeba ze sítě v kWh,
  - `ISC1` – činná dodávka/přetok do sítě jako čtvrthodinový výkon v kW,
  - `ISQ2` – činná dodávka/přetok do sítě v kWh.

## Typ měření a profil

EG.D OpenAPI podle dokumentace neposílá samostatný parametr „typ měření“. Důležitý je parametr `profile`.

Pokud máte u odběrného místa typ měření **C1**, do pole **Profil** typicky zadejte:

| Chci číst | Profil | Jednotka | Poznámka |
| --- | --- | --- | --- |
| spotřebu ze sítě jako čtvrthodinový výkon | `ICC1` | kW | výchozí volba integrace |
| spotřebu ze sítě jako energii | `ICQ2` | kWh | podle dokumentace dostupné od 1. 7. 2024 |
| přetok/dodávku do sítě jako čtvrthodinový výkon | `ISC1` | kW | pokud máte výrobu |
| přetok/dodávku do sítě jako energii | `ISQ2` | kWh | podle dokumentace dostupné od 1. 7. 2024 |

Pro Home Assistant statistiky bývá praktičtější profil v kWh (`ICQ2`/`ISQ2`), pokud ho EG.D pro vaše odběrné místo vrací. Pokud API vrací jen C1 výkon, použijte `ICC1`/`ISC1`; integrační senzor energie za období ho přepočítá z kW na kWh jako součet čtvrthodinových výkonů dělený 4.

## Konfigurace

V portálu Distribuce24 / EG.D si v části vzdáleného přístupu OpenAPI vygenerujte:

- `client_id`,
- `client_secret`,
- EAN/EIC odběrného místa,
- kód profilu, například `ICC1`, `ICQ2`, `ISC1` nebo `ISQ2`.

Integrace data načítá jednou denně, protože EG.D měřená data aktualizuje denně a dokumentace varuje před zbytečně častým voláním API. Rozsah dotazu vždy končí nejpozději včera ve 23:45 UTC, protože EG.D odmítá hodnoty `from`/`to` zasahující do dnešního dne.

## Řešení problémů

Pokud se při přidání integrace zobrazí `cannot_connect`, integrace při ověření kontroluje pouze platnost `client_id` / `client_secret` a dostupnost API číselníku statusů. Nevyžaduje už existující měřená data za poslední dny, protože ta mohou být u správně nastaveného odběrného místa dočasně prázdná.

Zkontrolujte hlavně:

- že používáte `client_id` a `client_secret` pro vzdálený přístup OpenAPI,
- že v EG.D / Distribuce24 portálu je vzdálený přístup aktivní,
- že Home Assistant má přístup na `https://idm.distribuce24.cz` a `https://data.distribuce24.cz`,
- že profil odpovídá tomu, co vám API pro dané odběrné místo vrací; pro typ měření C1 zkuste nejdřív `ICC1`.
