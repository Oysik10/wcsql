CREATE DATABASE IF NOT EXISTS worldcup CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE worldcup;

DROP TABLE IF EXISTS player_events;
DROP TABLE IF EXISTS match_players;
DROP TABLE IF EXISTS matches;
DROP TABLE IF EXISTS tournaments;

CREATE TABLE tournaments (
    year INT PRIMARY KEY,
    country VARCHAR(100),
    winner VARCHAR(100),
    runners_up VARCHAR(100),
    third VARCHAR(100),
    fourth VARCHAR(100),
    goals_scored INT,
    teams INT,
    games INT,
    attendance INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE matches (
    match_id INT PRIMARY KEY,
    round_id INT,
    year INT,
    datetime VARCHAR(50),
    stage VARCHAR(100),
    stadium VARCHAR(200),
    city VARCHAR(100),
    home_team VARCHAR(100),
    home_team_initials VARCHAR(10),
    away_team VARCHAR(100),
    away_team_initials VARCHAR(10),
    home_goals INT,
    away_goals INT,
    halftime_home INT,
    halftime_away INT,
    win_conditions VARCHAR(200),
    attendance INT,
    referee VARCHAR(200),
    INDEX idx_year (year),
    INDEX idx_home_team (home_team),
    INDEX idx_away_team (away_team),
    FOREIGN KEY (year) REFERENCES tournaments(year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE match_players (
    id INT AUTO_INCREMENT PRIMARY KEY,
    match_id INT,
    round_id INT,
    team_initials VARCHAR(10),
    coach_name VARCHAR(200),
    lineup CHAR(1),
    shirt_number INT,
    player_name VARCHAR(200),
    position VARCHAR(10),
    event_raw VARCHAR(500),
    INDEX idx_match_id (match_id),
    INDEX idx_player_name (player_name(100)),
    FOREIGN KEY (match_id) REFERENCES matches(match_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE player_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    match_id INT,
    round_id INT,
    team_initials VARCHAR(10),
    player_name VARCHAR(200),
    event_type VARCHAR(10),
    minute INT,
    INDEX idx_match_id (match_id),
    INDEX idx_player_name (player_name(100)),
    INDEX idx_event_type (event_type),
    FOREIGN KEY (match_id) REFERENCES matches(match_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
