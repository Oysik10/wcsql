#!/usr/bin/env python3
"""Build worldcup.db (SQLite) from the CSV files. Run once locally."""

import csv
import os
import re
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'worldcup.db')
CSV_DIR = os.path.dirname(os.path.abspath(__file__))

SCHEMA = '''
CREATE TABLE IF NOT EXISTS tournaments (
    year         INTEGER PRIMARY KEY,
    country      TEXT,
    winner       TEXT,
    runners_up   TEXT,
    third        TEXT,
    fourth       TEXT,
    goals_scored INTEGER,
    teams        INTEGER,
    games        INTEGER,
    attendance   INTEGER
);

CREATE TABLE IF NOT EXISTS matches (
    match_id            INTEGER PRIMARY KEY,
    round_id            INTEGER,
    year                INTEGER,
    datetime            TEXT,
    stage               TEXT,
    stadium             TEXT,
    city                TEXT,
    home_team           TEXT,
    home_team_initials  TEXT,
    away_team           TEXT,
    away_team_initials  TEXT,
    home_goals          INTEGER,
    away_goals          INTEGER,
    halftime_home       INTEGER,
    halftime_away       INTEGER,
    win_conditions      TEXT,
    attendance          INTEGER,
    referee             TEXT
);

CREATE INDEX IF NOT EXISTS idx_matches_year      ON matches(year);
CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches(home_team);
CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches(away_team);

CREATE TABLE IF NOT EXISTS match_players (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id      INTEGER,
    round_id      INTEGER,
    team_initials TEXT,
    coach_name    TEXT,
    lineup        TEXT,
    shirt_number  INTEGER,
    player_name   TEXT,
    position      TEXT,
    event_raw     TEXT
);

CREATE INDEX IF NOT EXISTS idx_mp_match_id    ON match_players(match_id);
CREATE INDEX IF NOT EXISTS idx_mp_player_name ON match_players(player_name);

CREATE TABLE IF NOT EXISTS player_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id      INTEGER,
    round_id      INTEGER,
    team_initials TEXT,
    player_name   TEXT,
    event_type    TEXT,
    minute        INTEGER
);

CREATE INDEX IF NOT EXISTS idx_pe_match_id    ON player_events(match_id);
CREATE INDEX IF NOT EXISTS idx_pe_player_name ON player_events(player_name);
'''


def clean_team(name):
    return re.sub(r'^rn\">', '', name.strip())


def safe_int(val, default=0):
    try:
        return int(re.sub(r'[^\d]', '', str(val)))
    except (ValueError, TypeError):
        return default


def parse_events(event_str, match_id, round_id, team, player):
    events = []
    if not event_str or not event_str.strip():
        return events
    for token in event_str.strip().split():
        m = re.match(r'^(RSY|IH|OH|MP|[GYWRPIO])(\d+)', token)
        if m:
            events.append((match_id, round_id, team, player, m.group(1), int(m.group(2))))
    return events


def build():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f'Removed old {DB_PATH}')

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    # ── Tournaments ──────────────────────────────────────────────────────────
    print('Importing tournaments...')
    rows = []
    with open(f'{CSV_DIR}/worldcups.csv', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            rows.append((
                safe_int(row['year']),
                row['host'].strip(),
                row['winner'].strip(),
                row['second'].strip(),
                row['third'].strip(),
                row['fourth'].strip(),
                safe_int(row['goals_scored']),
                safe_int(row['teams']),
                safe_int(row['games']),
                safe_int(row['attendance']),
            ))
    conn.executemany('INSERT INTO tournaments VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
    print(f'  {len(rows)} tournaments')

    # ── Matches ──────────────────────────────────────────────────────────────
    print('Importing matches...')
    rows = []
    seen = set()
    with open(f'{CSV_DIR}/WorldCupMatches.csv', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            mid = safe_int(row['MatchID'])
            if not mid or mid in seen:
                continue
            seen.add(mid)
            att = re.sub(r'[^\d]', '', row.get('Attendance', '') or '')
            rows.append((
                mid,
                safe_int(row['RoundID']),
                safe_int(row['Year']),
                row['Datetime'].strip(),
                row['Stage'].strip(),
                row['Stadium'].strip(),
                row['City'].strip(),
                clean_team(row['Home Team Name']),
                row['Home Team Initials'].strip(),
                clean_team(row['Away Team Name']),
                row['Away Team Initials'].strip(),
                safe_int(row['Home Team Goals']),
                safe_int(row['Away Team Goals']),
                safe_int(row['Half-time Home Goals']),
                safe_int(row['Half-time Away Goals']),
                row['Win conditions'].strip(),
                int(att) if att else 0,
                row['Referee'].strip(),
            ))
    conn.executemany(
        'INSERT INTO matches VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
        rows
    )
    print(f'  {len(rows)} matches')

    # ── Players & Events ─────────────────────────────────────────────────────
    print('Importing players and events...')
    player_rows, event_rows = [], []
    seen_players = set()
    with open(f'{CSV_DIR}/WorldCupPlayers.csv', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            mid = safe_int(row['MatchID'])
            rid = safe_int(row['RoundID'])
            if not mid:
                continue
            team   = row['Team Initials'].strip()
            player = row['Player Name'].strip()
            ev_raw = row.get('Event', '').strip()

            key = (mid, team, player)
            if key not in seen_players:
                seen_players.add(key)
                shirt = row['Shirt Number'].strip()
                player_rows.append((
                    mid, rid, team,
                    row['Coach Name'].strip(),
                    row['Line-up'].strip(),
                    int(shirt) if shirt.isdigit() else 0,
                    player,
                    row['Position'].strip(),
                    ev_raw,
                ))

            event_rows.extend(parse_events(ev_raw, mid, rid, team, player))

    conn.executemany(
        'INSERT INTO match_players (match_id,round_id,team_initials,coach_name,lineup,'
        'shirt_number,player_name,position,event_raw) VALUES (?,?,?,?,?,?,?,?,?)',
        player_rows
    )
    conn.executemany(
        'INSERT INTO player_events (match_id,round_id,team_initials,player_name,event_type,minute)'
        ' VALUES (?,?,?,?,?,?)',
        event_rows
    )
    print(f'  {len(player_rows)} player records, {len(event_rows)} events')

    conn.commit()
    conn.close()
    size_kb = os.path.getsize(DB_PATH) // 1024
    print(f'\nDone! worldcup.db created ({size_kb} KB)')


if __name__ == '__main__':
    build()
