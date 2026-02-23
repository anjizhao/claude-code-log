-- Render flags for cache invalidation when display options change
-- Migration: 005
-- Description: Track show_stats and skip_combined flags in cached HTML entries

ALTER TABLE html_cache ADD COLUMN show_stats INTEGER NOT NULL DEFAULT 0;
ALTER TABLE html_cache ADD COLUMN skip_combined INTEGER NOT NULL DEFAULT 0;

ALTER TABLE html_pages ADD COLUMN show_stats INTEGER NOT NULL DEFAULT 0;

-- Clear cached HTML to force regeneration: pre-migration entries have unknown
-- render flag state (show_stats was always on, skip_combined could be either)
DELETE FROM html_cache;
DELETE FROM html_pages;
