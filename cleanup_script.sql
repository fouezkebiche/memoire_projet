-- Backup the database before making changes
-- Run this command in the terminal:
-- pg_dump -U odoo_user api_integration > api_integration_backup_20250516_4.sql

-- Begin transaction to ensure atomicity
BEGIN;

-- Delete line stations to avoid foreign key constraints
DELETE FROM infrastructure_line_station;

-- Delete lines to clear station references
DELETE FROM infrastructure_line;

-- Delete all stations
DELETE FROM infrastructure_station;

-- Reset all sync-related configuration parameters
DELETE FROM ir_config_parameter 
WHERE key LIKE 'infrastructure%.last_sync';

-- Commit transaction
COMMIT;

-- Verify cleanup
SELECT 'Stations count', COUNT(*) FROM infrastructure_station;  -- Should be 0
SELECT 'Lines count', COUNT(*) FROM infrastructure_line;      -- Should be 0
SELECT 'Line stations count', COUNT(*) FROM infrastructure_line_station; -- Should be 0
SELECT 'Sync parameters count', COUNT(*) FROM ir_config_parameter 
WHERE key LIKE 'infrastructure%.last_sync'; -- Should be 0
SELECT 'Sample stations', id, external_id, name_en 
FROM infrastructure_station LIMIT 5; -- Should return 0 rows