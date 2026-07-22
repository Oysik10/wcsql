import os
import re
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, g

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'worldcup.db')


@app.template_filter('parse_event_tokens')
def parse_event_tokens(event_raw):
    if not event_raw:
        return []
    result = []
    for token in event_raw.strip().split():
        m = re.match(r'^(RSY|IH|OH|MP|[GYWRPIO])(\d+)', token)
        if m:
            result.append({'type': m.group(1), 'minute': m.group(2)})
    return result


EVENT_LABELS = {
    'G':   ('Goal', '⚽'),
    'P':   ('Penalty Goal', '🎯'),
    'W':   ('Own Goal', '😬'),
    'Y':   ('Yellow Card', '🟨'),
    'R':   ('Red Card', '🟥'),
    'RSY': ('Red Card (2nd Yellow)', '🟥'),
    'MP':  ('Missed Penalty', '❌'),
    'I':   ('Substitution In', '↑'),
    'IH':  ('Sub In (Half-time)', '↑'),
    'O':   ('Substitution Out', '↓'),
    'OH':  ('Sub Out (Half-time)', '↓'),
}

STAGE_ORDER = [
    'Group 1', 'Group 2', 'Group 3', 'Group 4', 'Group 5', 'Group 6',
    'Group 7', 'Group 8', 'Pool 1', 'Pool 2', 'Pool 3', 'Pool 4',
    'Group A', 'Group B', 'Group C', 'Group D',
    'Group E', 'Group F', 'Group G', 'Group H',
    'First round', 'Preliminary round', 'First Group Stage', 'Second Group Stage',
    'Round of 16', 'Quarter-finals', 'Semi-finals',
    'Play-off for third place', 'Third place', 'Match for third place',
    'Final',
]

def stage_sort_key(stage):
    try:
        return STAGE_ORDER.index(stage)
    except ValueError:
        return -1


def get_db():
    if 'db' not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    rows = get_db().execute(sql, args).fetchall()
    rows = [dict(r) for r in rows]
    return (rows[0] if rows else None) if one else rows


@app.context_processor
def inject_helpers():
    return {'event_labels': EVENT_LABELS, 'stage_sort_key': stage_sort_key}


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


@app.route('/')
def home():
    tournaments = query('SELECT * FROM tournaments ORDER BY year')
    return render_template('home.html', tournaments=tournaments)


@app.route('/worldcup/<int:year>')
def worldcup(year):
    tournament = query('SELECT * FROM tournaments WHERE year = ?', (year,), one=True)
    if not tournament:
        return 'Tournament not found', 404
    matches = query('SELECT * FROM matches WHERE year = ? ORDER BY datetime', (year,))
    stages = {}
    for m in matches:
        stages.setdefault(m['stage'], []).append(m)
    ordered_stages = sorted(stages.items(), key=lambda kv: stage_sort_key(kv[0]))
    return render_template('worldcup.html', tournament=tournament, stages=ordered_stages)


@app.route('/team/<path:team_name>')
def team(team_name):
    matches = query(
        'SELECT * FROM matches WHERE home_team = ? OR away_team = ? ORDER BY year, datetime',
        (team_name, team_name)
    )
    by_year = {}
    for m in matches:
        by_year.setdefault(m['year'], []).append(m)
    return render_template('team.html', team_name=team_name, matches=matches, by_year=by_year)


@app.route('/teams')
def teams():
    all_teams = query(
        'SELECT DISTINCT home_team as name FROM matches '
        'UNION SELECT DISTINCT away_team FROM matches ORDER BY name'
    )
    return render_template('teams.html', teams=all_teams)


@app.route('/match/<int:match_id>')
def match(match_id):
    m = query('SELECT * FROM matches WHERE match_id = ?', (match_id,), one=True)
    if not m:
        return 'Match not found', 404
    players = query(
        'SELECT * FROM match_players WHERE match_id = ? ORDER BY team_initials, lineup DESC, shirt_number',
        (match_id,)
    )
    events = query(
        'SELECT * FROM player_events WHERE match_id = ? ORDER BY minute, id',
        (match_id,)
    )
    home_init = m['home_team_initials']
    away_init = m['away_team_initials']
    return render_template('match.html', match=m,
                           home_starters=[p for p in players if p['team_initials'] == home_init and p['lineup'] == 'S'],
                           home_subs    =[p for p in players if p['team_initials'] == home_init and p['lineup'] != 'S'],
                           away_starters=[p for p in players if p['team_initials'] == away_init and p['lineup'] == 'S'],
                           away_subs    =[p for p in players if p['team_initials'] == away_init and p['lineup'] != 'S'],
                           home_events  =[e for e in events if e['team_initials'] == home_init],
                           away_events  =[e for e in events if e['team_initials'] == away_init],
                           all_events   =events)


@app.route('/player/<path:player_name>')
def player(player_name):
    appearances = query(
        '''SELECT mp.*, m.year, m.stage, m.home_team, m.away_team,
                  m.home_goals, m.away_goals, m.match_id,
                  m.home_team_initials, m.away_team_initials, m.datetime
           FROM match_players mp
           JOIN matches m ON mp.match_id = m.match_id
           WHERE mp.player_name = ?
           ORDER BY m.year, m.datetime''',
        (player_name,)
    )
    events = query(
        '''SELECT pe.*, m.year, m.stage, m.home_team, m.away_team,
                  m.home_goals, m.away_goals, m.home_team_initials
           FROM player_events pe
           JOIN matches m ON pe.match_id = m.match_id
           WHERE pe.player_name = ?
           ORDER BY m.year, m.datetime, pe.minute''',
        (player_name,)
    )
    stats = {}
    for e in events:
        stats[e['event_type']] = stats.get(e['event_type'], 0) + 1
    return render_template('player.html', player_name=player_name,
                           appearances=appearances, events=events, stats=stats)


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return redirect(url_for('home'))
    like = f'%{q}%'
    players = query(
        'SELECT DISTINCT player_name FROM match_players WHERE player_name LIKE ? ORDER BY player_name LIMIT 30',
        (like,)
    )
    teams = query(
        'SELECT DISTINCT home_team as name FROM matches WHERE home_team LIKE ? '
        'UNION SELECT DISTINCT away_team FROM matches WHERE away_team LIKE ? ORDER BY name',
        (like, like)
    )
    return render_template('search.html', q=q, players=players, teams=teams)


if __name__ == '__main__':
    app.run(debug=True, port=5001)
