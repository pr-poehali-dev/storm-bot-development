CREATE TABLE IF NOT EXISTS users (
    telegram_id BIGINT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT 'Охотник',
    balance INTEGER NOT NULL DEFAULT 5000,
    boost_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_cars (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL REFERENCES users(telegram_id),
    car_id INTEGER NOT NULL CHECK (car_id BETWEEN 1 AND 10),
    level INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 3),
    broken BOOLEAN NOT NULL DEFAULT FALSE,
    bought_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (telegram_id, car_id)
);

CREATE INDEX IF NOT EXISTS idx_user_cars_telegram_id ON user_cars(telegram_id);
