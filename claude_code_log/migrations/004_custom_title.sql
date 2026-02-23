-- Add custom_title column for user-set session titles (via /rename command)
ALTER TABLE sessions ADD COLUMN custom_title TEXT;
