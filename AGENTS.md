# Rathsnetz - Brewery Management System

Django web application for managing a home brewery. Specially designed for [braurat.de](https://braurat.de).

## Tech Stack

- **Framework**: Django 4.2
- **Frontend**: Bootstrap 5, Crispy Forms
- **Visualization**: Plotly, Kaleido
- **Data Processing**: Pandas, NumPy
- **PDF Generation**: ReportLab
- **Time Series DB**: InfluxDB
- **QR Codes**: django-qr-code, segno
- **Database**: SQLite (default), MySQL (configurable)

## Project Structure

```
rathsnetz/
├── brewery/              # Main app
│   ├── models/          # Database models
│   ├── templates/       # HTML templates
│   ├── templatetags/   # Custom template tags
│   ├── views.py        # View functions
│   ├── forms.py       # Form classes
│   ├── urls.py        # URL routing
│   ├── admin.py      # Django admin config
│   ├── utils.py      # Utility functions
│   └── ispindel.py   # iSpindel integration
├── rathsnetz/          # Django project settings
├── static/             # Static files
└── db.sqlite3          # SQLite database
```

## Database Models

Key models (see `BR_UML.txt` for full diagram):

| Model                  | Description                          |
| ---------------------- | ------------------------------------ |
| `Recipe`               | Beer recipes with water calculations |
| `RecipeBrewStep`       | Individual brewing steps             |
| `Charge`               | Brewing session (links to Recipe)    |
| `BrewProtocol`         | Recorded brewing steps               |
| `FermentationProtocol` | Fermentation tracking                |
| `Storage`              | Ingredient inventory                 |
| `Keg`                  | Keg management                       |
| `Account`              | Financial tracking                   |
| `HopCalculation`       | Glenn Tinseth hop formula            |

## URL Routes

| URL                    | View               | Description         |
| ---------------------- | ------------------ | ------------------- |
| `/`                    | `index`            | Landing page        |
| `/impressum/`          | `impressum`        | Legal/imprint       |
| `/analyse/`            | `analyse`          | Analytics dashboard |
| `/brewing/`            | `brewing_overview` | Charge list         |
| `/brewing/add/`        | `brewing_add`      | New brewing session |
| `/brewing/<cid>/`      | `brewing`          | Brewing protocol    |
| `/recipe/`             | `recipe`           | Recipe list         |
| `/recipe/add/`         | `recipe_add`       | New recipe          |
| `/recipe/<id>/`        | `recipe_detail`    | Recipe details      |
| `/recipe/<id>/export/` | `recipe_export`    | Export BeerXML      |
| `/recipe/import/`      | `recipe_import`    | Import BeerXML      |
| `/storage/`            | `storage`          | Inventory           |
| `/keg/`                | `keg`              | Keg management      |
| `/fermentation/<cid>/` | `fermentation`     | Fermentation data   |

## Configuration

Environment settings are stored in `static/config/config.json`:

```json
{
    "influxdb": [...],
    "django": [{"secretkey": "..."}]
}
```

## Commands

```bash
# Run development server
python manage.py runserver

# Run tests
python manage.py test

# Create migrations
python manage.py makemigrations
python manage.py migrate

# Collect static files
python manage.py collectstatic

# Django shell
python manage.py shell
```

## External Integrations

### iSpindel

- Endpoint: `/spindel/` (POST)
- Receives temperature/gravity data from iSpindel devices
- Stores in InfluxDB

### InfluxDB

- Used for time series data (temperature, gravity)
- Configure in `static/config/config.json`

## Conventions

- **Forms**: Django ModelForm with crispy-forms
- **Templates**: Bootstrap 5, extends `base.html`
- **Testing**: `python manage.py test`
- **i18n**: German (`LANGUAGE_CODE = "de"`)

## Known Features

- BeerXML import/export for recipes
- Glenn Tinseth hop alpha acid calculation
- QR code generation for recipe sharing
- Public protocol sharing via riddle link
