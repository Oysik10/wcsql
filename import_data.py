#!/usr/bin/env python3
"""Import World Cup CSV data into MySQL database."""

import csv
import os
import re
import sys
import pymysql

# ── Config ────────────────────────────────────────────────────────────────────
DB_CONFIG = {
    'host':     os.environ.get('DB_HOST', 'localhost'),
    'port':     int(os.environ.get('DB_PORT', 3306)),
    'user':     os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'db':       os.environ.get('DB_NAME', 'worldcup'),
    'charset':  'utf8mb4',
}

CSV_DIR = '.'   # directory containing the CSVs

# ── Helpers ───────────────────────────────────────────────────────────────────
def clean_team(name):
    """Fix HTML-artifact team names like 'rn\">Bosnia and Herzegovina'."""
    return re.sub(r'^rn\">', '', name.strip())

def safe_int(val, default=0):
    try:
        return int(str(val).replace(',', '').replace('.', '').strip())
    except (ValueError, TypeError):
        return default

EVENT_LABELS = {
    'G':   'Goal',
    'P':   'Penalty Goal',
    'W':   'Own Goal',
    'Y':   'Yellow Card',
    'R':   'Red Card',
    'RSY': 'Red Card (2nd Yellow)',
    'MP':  'Missed Penalty',
    'I':   'Substitution In',
    'IH':  'Substitution In (HT)',
    'O':   'Substitution Out',
    'OH':  'Substitution Out (HT)',
}

def parse_events(event_str, match_id, round_id, team_initials, player_name):
    """Parse event string like \"G40' Y78'\" into a list of event dicts."""
    events = []
    if not event_str or not event_str.strip():
        return events
    for token in event_str.strip().split():
        m = re.match(r'^(RSY|IH|OH|MP|[GYWRPIO])(\d+)\'?(?:\+\d+)?$', token)
        if m:
            events.append({
                'match_id': match_id,
                'round_id': round_id,
                'team_initials': team_initials,
                'player_name': player_name,
                'event_type': m.group(1),
                'minute': int(m.group(2)),
            })
    return events

# ── Import functions ──────────────────────────────────────────────────────────
def import_tournaments(cursor):
    print('Importing tournaments...')
    with open(f'{CSV_DIR}/worldcups.csv', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
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
    cursor.executemany(
        'INSERT INTO tournaments VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
        rows
    )
    print(f'  Inserted {len(rows)} tournaments.')


def import_matches(cursor):
    print('Importing matches...')
    rows = []
    seen_match_ids = set()
    with open(f'{CSV_DIR}/WorldCupMatches.csv', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            match_id = safe_int(row['MatchID'])
            if not match_id or match_id in seen_match_ids:
                continue
            seen_match_ids.add(match_id)
            attendance_raw = re.sub(r'[^\d]', '', row.get('Attendance', '0') or '0')
            rows.append((
                match_id,
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
                safe_int(attendance_raw) if attendance_raw else 0,
                row['Referee'].strip(),
            ))
    cursor.executemany(
        '''INSERT INTO matches
           (match_id,round_id,year,datetime,stage,stadium,city,
            home_team,home_team_initials,away_team,away_team_initials,
            home_goals,away_goals,halftime_home,halftime_away,
            win_conditions,attendance,referee)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
        rows
    )
    print(f'  Inserted {len(rows)} matches.')


def import_players(cursor):
    print('Importing players and events...')
    player_rows = []
    event_rows = []
    seen_player_ids = set()

    with open(f'{CSV_DIR}/WorldCupPlayers.csv', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            match_id = safe_int(row['MatchID'])
            round_id = safe_int(row['RoundID'])
            if not match_id:
                continue

            team = row['Team Initials'].strip()
            player = row['Player Name'].strip()
            event_raw = row.get('Event', '').strip()

            # Deduplicate players per match (same player can appear multiple times)
            key = (match_id, team, player)
            if key not in seen_player_ids:
                seen_player_ids.add(key)
                shirt = row['Shirt Number'].strip()
                player_rows.append((
                    match_id,
                    round_id,
                    team,
                    row['Coach Name'].strip(),
                    row['Line-up'].strip(),
                    safe_int(shirt) if shirt.isdigit() else 0,
                    player,
                    row['Position'].strip(),
                    event_raw,
                ))

            # Parse events
            for ev in parse_events(event_raw, match_id, round_id, team, player):
                event_rows.append((
                    ev['match_id'],
                    ev['round_id'],
                    ev['team_initials'],
                    ev['player_name'],
                    ev['event_type'],
                    ev['minute'],
                ))

    # Batch insert players
    cursor.executemany(
        '''INSERT INTO match_players
           (match_id,round_id,team_initials,coach_name,lineup,
            shirt_number,player_name,position,event_raw)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
        player_rows
    )
    print(f'  Inserted {len(player_rows)} player records.')

    cursor.executemany(
        '''INSERT INTO player_events
           (match_id,round_id,team_initials,player_name,event_type,minute)
           VALUES (%s,%s,%s,%s,%s,%s)''',
        event_rows
    )
    print(f'  Inserted {len(event_rows)} events.')


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SET NAMES utf8mb4')
        cursor.execute('SET foreign_key_checks = 0')

        import_tournaments(cursor)
        import_matches(cursor)
        import_players(cursor)

        cursor.execute('SET foreign_key_checks = 1')
        conn.commit()
        print('\nAll data imported successfully!')

    except pymysql.Error as e:
        print(f'MySQL error: {e}', file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f'CSV file not found: {e}', file=sys.stderr)
        print('Run this script from the directory containing the CSV files.')
        sys.exit(1)
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


if __name__ == '__main__':
    main()
