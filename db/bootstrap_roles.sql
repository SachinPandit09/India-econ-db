-- One-time server setup, part 2. Run as postgres after bootstrap.sql, before `econdb migrate`.
-- Group roles only (no login, no passwords). Touches only econdb roles.
CREATE ROLE econdb_writer NOLOGIN;    -- pipeline privileges, used via SET ROLE econdb_writer
CREATE ROLE econdb_reader NOLOGIN;    -- read-only group; people/tools become members later
GRANT econdb_writer TO econdb_owner;  -- lets pipeline sessions of econdb_owner do SET ROLE econdb_writer
