# EG.D Distribution for Home Assistant

Custom integration for reading measured electricity profile data from the EG.D / Distribuce24 OpenAPI.

## Features

- OAuth2 client-credentials authentication against `https://idm.distribuce24.cz/oauth/token`.
- Reads profile values from `https://data.distribuce24.cz/rest/spotreby`.
- Creates sensors for the latest valid measurement and a sum over the configured time window.
- Supports common EG.D profile codes, for example `ICQ2` for active consumption energy in kWh and `ISQ2` for active delivery energy in kWh.

## Installation

Copy `custom_components/egd_distribution` to the `custom_components` directory in your Home Assistant config directory and restart Home Assistant.

Then add **EG.D Distribution** from **Settings → Devices & services → Add integration**.

## Configuration

You need credentials generated in the Distribuce24 portal under remote access / OpenAPI:

- `client_id`
- `client_secret`
- EAN/EIC of the metering point
- Profile code, for example `ICQ2`, `ISQ2`, `ICC1`, or `ISC1`

EG.D updates data daily. The integration polls once per day to avoid unnecessary load on the distributor API.
