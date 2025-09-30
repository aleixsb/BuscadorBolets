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
