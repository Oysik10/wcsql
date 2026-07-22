# World Cup Explorer

A web app for digging through the history of the FIFA World Cup — all 21 tournaments from 1930 to 2018, browsable by tournament or by team, with search across players and nations. Under the hood it's really an exercise in modeling structured data well and querying it cleanly: a SQL database, a schema I designed, and the queries that power each view.

**[Live demo →](https://wcsql.vercel.app)**

## What you can do

| Page | Path | What's there |
|------|------|--------------|
| Home | `/` | Every World Cup tournament, 1930–2018 |
| Tournament | `/worldcup/<year>` | That year's matches, grouped by stage |
| Team | `/team/<name>` | Every match a nation played, with stats |
| Match | `/match/<id>` | Lineups, subs, goals, cards |
| Player | `/player/<name>` | A player's full set of appearances and events |
| All Teams | `/teams` | Browse every nation |
| Search | `/search?q=…` | Find players and teams |

Match events — goals, penalties, own goals, cards, substitutions — get parsed out of the raw data and rendered with readable labels.

## The interesting parts

The database schema, the queries powering each view, and routing cleanly across the whole dataset. Most of the work was in the modeling: ~37,000 player rows and 850+ matches only become a browsable app once the relationships between tournaments, matches, teams, and players are right.

## Built with

Python · Flask · SQLite · Jinja2 · deployed on Vercel

The database (`worldcup.db`) ships with the repo, so it runs with zero setup.

## Running it locally

You'll need Python 3.10+.

```bash
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:5001>.

To rebuild the database from the source CSVs:

```bash
python build_db.py
```

## Layout

```
app.py         Flask app and routes
build_db.py    Builds worldcup.db from the CSVs
schema.sql     The database schema
worldcup.db    Prebuilt SQLite database
templates/     Jinja2 templates
static/        CSS
*.csv          Source datasets
```

## Data

Public FIFA World Cup datasets — tournament summaries, 850+ matches with scores, stadiums, and referees, and ~37,000 player rows.
