"""Versioned additive schema bootstrap for existing Nudge installations."""
from sqlalchemy import Column, String, Table, MetaData, select, text
from app.database import Base, engine

metadata = MetaData()
versions = Table("schema_migrations", metadata, Column("version", String(80), primary_key=True))

def migrate():
    import app.db_models  # Register tables before applying the baseline.
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(73482105)"))
        metadata.create_all(connection)
        applied = set(connection.execute(select(versions.c.version)).scalars())
        if "0001_revisioned_workspaces" not in applied:
            # All legacy tables are retained; new tables are created in dependency order.
            Base.metadata.create_all(connection)
            connection.execute(versions.insert().values(version="0001_revisioned_workspaces"))

if __name__ == "__main__":
    migrate()
    print("Schema is up to date (0001_revisioned_workspaces).")
