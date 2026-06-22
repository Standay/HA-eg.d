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
- Senzor součtu platných hodnot za nastavené období.
- Podpora běžných profilů EG.D, například:
  - `ICQ2` – činná spotřeba ze sítě v kWh,
  - `ISQ2` – činná dodávka/přetok do sítě v kWh,
  - `ICC1` – činná spotřeba jako čtvrthodinový výkon v kW,
  - `ISC1` – činná dodávka jako čtvrthodinový výkon v kW.

## Konfigurace

V portálu Distribuce24 / EG.D si v části vzdáleného přístupu OpenAPI vygenerujte:

- `client_id`,
- `client_secret`,
- EAN/EIC odběrného místa,
- kód profilu, například `ICQ2`, `ISQ2`, `ICC1` nebo `ISC1`.

Integrace data načítá jednou denně, protože EG.D měřená data aktualizuje denně a dokumentace varuje před zbytečně častým voláním API.
