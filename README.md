# BuscadorBolets

Eines per obtenir informació meteorològica amb l'objectiu de trobar bones
zones de bolets. Aquest repositori comença amb un script que descarrega les
precipitacions diàries de totes les estacions Meteocat disponibles i genera
acumulats setmanals, mensuals i anuals.

## Requisits

* Python 3.11 o superior
* Un compte a [Meteocat API](https://apidocs.meteocat.gencat.cat/) amb clau d'accés
* Les dependències definides a `requirements.txt`

Instal·la-les amb:
=======
## Requisits previs

Per executar els scripts que consulten l'API del Meteocat necessites una clau
personal (`x-api-key`). La pots sol·licitar gratuïtament a
[apidocs.meteo.cat](https://apidocs.meteo.cat/). Desa-la en una variable
d'entorn anomenada `METEOCAT_API_KEY` o passa-la explícitament amb l'opció
`--api-key`.

Recomanem utilitzar un entorn virtual de Python 3.10 o superior i instal·lar les
dependències necessàries amb:

```bash
pip install -r requirements.txt
```

## Ús

El script principal està disponible com a mòdul executant el CLI següent:

```bash
python -m meteocat.cli --output dades/precipitacio.json --api-key "$METEOCAT_API_KEY"
```

Per defecte descarrega totes les estacions actives de la xarxa XEMA des de l'1
d'agost (de l'any actual si encara no hem passat l'agost, si no de l'any
anterior) fins avui. Pots personalitzar-lo amb aquests paràmetres:

* `--start-date` i `--end-date`: dates en format ISO (YYYY-MM-DD).
* `--network`: codi de la xarxa d'estacions (per defecte `XEMA`).
* `--station-status`: filtra per l'estat de l'estació (`operativa`, `tancada`, ...).
* `--variable-code`: codi de la variable de precipitació (per defecte `35`).
* `--log-level`: nivell de log (`DEBUG`, `INFO`, `WARNING`, ...).

La sortida és un fitxer JSON amb les dades següents:

```json
{
  "generated_at": "2024-09-30T18:05:00Z",
  "start_date": "2024-08-01",
  "end_date": "2024-09-30",
  "station_count": 184,
  "series": [
    {
      "station": {
        "code": "UG",
        "name": "Ulldeter",
        "municipality": "Setcases",
        "coordinates": {"lat": 42.41, "lon": 2.28},
        "elevation": 2425
      },
      "daily": [
        {"date": "2024-08-01", "value": 0.0},
        {"date": "2024-08-02", "value": 1.4}
      ],
      "aggregated": {
        "weekly": [{"period": "2024-W31", "value": 7.2}],
        "monthly": [{"period": "2024-08", "value": 54.3}],
        "yearly": [{"period": "2024", "value": 220.7}]
      }
    }
  ]
}
```

> **Nota**: la infraestructura del test no pot accedir a l'API externa, de manera
> que els exemples superiors són il·lustratius. Si hi ha canvis a l'API caldrà
> ajustar els punts finals o les claus de les respostes al codi del client.

## Tests

```bash
pytest
```
=======
## Dades de vent diàries

El directori `scripts/` conté l'eina `fetch_wind_data.py`, que descarrega les
estadístiques diàries de velocitat (`VV10m`) i direcció (`DV10m`) del vent per a
totes les estacions de la xarxa XEMA disponibles des de l'1 d'agost (per defecte
prèn l'any actual) fins a la data actual.

Exemple d'ús mínim:

```bash
python scripts/fetch_wind_data.py
```

Paràmetres principals:

- `--start-date YYYY-MM-DD`: data inicial. Per defecte es fa servir l'1 d'agost
del mateix any.
- `--end-date YYYY-MM-DD`: data final. Per defecte és el dia d'avui.
- `--variable`: es pot indicar múltiples vegades per afegir codis de variables
  de vent diferents als valors per defecte (`VV10m`, `DV10m`).
- `--output`: ruta del fitxer CSV on desar les dades (per defecte
  `data/wind_daily.csv`).
- `--log-level`: canvia el nivell de detall dels missatges de log (`DEBUG`,
  `INFO`, `WARNING`, `ERROR`, `CRITICAL`).

El fitxer resultant inclou una fila per estació i dia amb les dades agregades de
vent disponibles a l'API del Meteocat.
