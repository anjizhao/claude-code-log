-- Render flags for cache invalidation when display options change
-- Migration: 005
-- Description: Track show_stats and skip_combined flags in cached HTML entries

ALTER TABLE html_cache ADD COLUMN show_stats INTEGER NOT NULL DEFAULT 0;
ALTER TABLE html_cache ADD COLUMN skip_combined INTEGER NOT NULL DEFAULT 0;

ALTER TABLE html_pages ADD COLUMN show_stats INTEGER NOT NULL DEFAULT 0;
