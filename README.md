# rathsnetz

Rathsnetz is a modern Django application for managing the full brewing workflow of a home brewery — from recipes and brewing sessions to fermentation tracking, storage, and reporting.

## Why this project exists

Rathsnetz was created to bring brewing administration into one place: recipe planning, brew day documentation, ingredient tracking, and analytical insights all in a single web interface.

## Highlights

- Recipe management with BeerXML import/export
- Brewing session and protocol tracking
- Fermentation and storage oversight
- Hop calculation and reporting tools
- QR code support and shareable protocol links
- Designed for the needs of [braurat.de](https://braurat.de)

## Technology

- Django 4.2
- Bootstrap 5 and Crispy Forms
- Plotly and Kaleido for visual reporting
- Pandas and NumPy for data handling
- ReportLab for PDF generation
- InfluxDB for time-series fermentation data
- SQLite by default, with MySQL support available through configuration

## Getting started

### Requirements

- Python 3.9 or newer
- pip
- a virtual environment

### Installation

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install project dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Apply database migrations:

   ```bash
   python manage.py migrate
   ```

4. Start the development server:

   ```bash
   python manage.py runserver
   ```

5. Open the application in your browser:
   ```text
   http://127.0.0.1:8000/
   ```

## Useful development commands

```bash
python manage.py test
python manage.py makemigrations
python manage.py migrate
python manage.py shell
```

## Configuration

Runtime settings and integration values are stored in:

- static/config/config.json

This file is used for configuration such as InfluxDB access and Django settings.

## Project structure

- `brewery/` — application logic, models, views, and templates
- `rathsnetz/` — Django project settings and routing

## Status

Rathsnetz is an active project with ongoing development and documentation improvements.
