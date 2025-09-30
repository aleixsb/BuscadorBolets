# BuscadorBolets

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
