"""
Migration script to add execution_source and live_trading_enabled fields to trades table
"""
from sqlalchemy import text
from db import engine

def upgrade():
    # Add execution_source column with default 'simulated'
    with engine.connect() as conn:
        # Add execution_source column
        conn.execute(text("""
            ALTER TABLE trades 
            ADD COLUMN execution_source VARCHAR(10) DEFAULT 'simulated' NOT NULL
        """))
        
        # Add live_trading_enabled column with default false
        conn.execute(text("""
            ALTER TABLE trades 
            ADD COLUMN live_trading_enabled BOOLEAN DEFAULT FALSE NOT NULL
        """))
        
        # Create enum type for execution_source if it doesn't exist
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'executionsource') THEN
                    CREATE TYPE executionsource AS ENUM ('simulated', 'manual', 'api_live');
                END IF;
            END
            $$;
        """))
        
        # Convert the column to use the enum type
        conn.execute(text("""
            ALTER TABLE trades 
            ALTER COLUMN execution_source TYPE executionsource 
            USING execution_source::executionsource;
        """))
        
        conn.commit()

def downgrade():
    # Remove the columns
    with engine.connect() as conn:
        # Drop the columns
        conn.execute(text("""
            ALTER TABLE trades 
            DROP COLUMN IF EXISTS execution_source,
            DROP COLUMN IF EXISTS live_trading_enabled;
        
            -- Only drop the enum type if no other tables are using it
            DROP TYPE IF EXISTS executionsource;
        """))
        conn.commit()

if __name__ == "__main__":
    print("Running migration: Adding execution metadata to trades table...")
    upgrade()
    print("Migration completed successfully.")
