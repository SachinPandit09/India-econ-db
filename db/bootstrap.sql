-- One-time server setup. Run as postgres, connected to the "postgres" DB. Touches only econdb objects.
CREATE ROLE econdb_owner LOGIN;
CREATE DATABASE econdb OWNER econdb_owner ENCODING 'UTF8' TEMPLATE template0;
REVOKE ALL ON DATABASE econdb FROM PUBLIC;
