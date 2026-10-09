CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise TEXT NOT NULL,
    sets INTEGER NOT NULL CHECK (sets > 0),
    reps INTEGER NOT NULL CHECK (reps > 0),
    weight REAL NOT NULL CHECK (weight >= 0),
    performed_on TEXT NOT NULL,  -- ISO date, YYYY-MM-DD
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workouts_performed_on ON workouts (performed_on);

CREATE TABLE IF NOT EXISTS body_weights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    weight_lb REAL NOT NULL CHECK (weight_lb > 0),
    measured_on TEXT NOT NULL,  -- ISO date, YYYY-MM-DD
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_body_weights_measured_on ON body_weights (measured_on);

CREATE TABLE IF NOT EXISTS foods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    serving TEXT NOT NULL,  -- free text, e.g. "1 cup" or "150 g"
    meal TEXT NOT NULL CHECK (meal IN ('breakfast', 'lunch', 'dinner', 'snack')),
    calories REAL NOT NULL CHECK (calories >= 0),
    protein_g REAL NOT NULL CHECK (protein_g >= 0),
    carbs_g REAL NOT NULL CHECK (carbs_g >= 0),
    fat_g REAL NOT NULL CHECK (fat_g >= 0),
    eaten_on TEXT NOT NULL,  -- ISO date, YYYY-MM-DD
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_foods_eaten_on ON foods (eaten_on);

-- Holds at most one row (id = 1). A NULL goal means "no goal set".
CREATE TABLE IF NOT EXISTS nutrition_goals (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    calories REAL CHECK (calories > 0),
    protein_g REAL CHECK (protein_g > 0),
    carbs_g REAL CHECK (carbs_g > 0),
    fat_g REAL CHECK (fat_g > 0),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
