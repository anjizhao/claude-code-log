-- Render flags for cache invalidation when display options change
-- Migration: 005
-- Description: Track show_stats and skip_combined flags in cached HTML entries

ALTER TABLE html_cache ADD COLUMN show_stats INTEGER NOT NULL DEFAULT 0;
ALTER TABLE html_cache ADD COLUMN skip_combined INTEGER NOT NULL DEFAULT 0;

ALTER TABLE html_pages ADD COLUMN show_stats INTEGER NOT NULL DEFAULT 0;

-- Backfill: pre-migration HTML was rendered with stats always visible
UPDATE html_cache SET show_stats = 1;
UPDATE html_pages SET show_stats = 1;
