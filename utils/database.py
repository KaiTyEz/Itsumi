import sqlite3
import os
from utils.katlog import logger

class Database:
    def __init__(self, db_path="db/bot.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = None
        self.cursor = None
        self.connect()
        self.init_tables()

    def connect(self):
        """Connect to the SQLite database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
        except Exception as e:
            logger.error(f"Database connection error: {e}")

    def init_tables(self):
        """Initialize database tables"""
        try:
            # Anti-link tables
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS antilink_config (
                    guild_id TEXT PRIMARY KEY,
                    enabled INTEGER DEFAULT 0,
                    UNIQUE(guild_id)
                )
            ''')
            
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS antilink_channels (
                    guild_id TEXT,
                    channel_id TEXT,
                    PRIMARY KEY (guild_id, channel_id),
                    FOREIGN KEY (guild_id) REFERENCES antilink_config(guild_id)
                )
            ''')
            
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS antilink_violations (
                    user_id TEXT,
                    guild_id TEXT,
                    count INTEGER DEFAULT 0,
                    last_violation TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            
            # Anti-raid tables
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS antiraid_config (
                    guild_id TEXT PRIMARY KEY,
                    enabled INTEGER DEFAULT 0,
                    verification_required INTEGER DEFAULT 1,
                    raid_threshold INTEGER DEFAULT 5,
                    time_window INTEGER DEFAULT 10,
                    verification_timeout INTEGER DEFAULT 300,
                    UNIQUE(guild_id)
                )
            ''')
            
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS antiraid_joins (
                    guild_id TEXT,
                    timestamp REAL,
                    FOREIGN KEY (guild_id) REFERENCES antiraid_config(guild_id)
                )
            ''')
            
            # Anti-nuke tables
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS antinuke_config (
                    guild_id TEXT PRIMARY KEY,
                    enabled INTEGER DEFAULT 0,
                    UNIQUE(guild_id)
                )
            ''')
            
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS antinuke_thresholds (
                    guild_id TEXT,
                    action TEXT,
                    count INTEGER DEFAULT 3,
                    window INTEGER DEFAULT 10,
                    PRIMARY KEY (guild_id, action),
                    FOREIGN KEY (guild_id) REFERENCES antinuke_config(guild_id)
                )
            ''')
            
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS antinuke_violations (
                    guild_id TEXT,
                    user_id TEXT,
                    action TEXT,
                    timestamp REAL,
                    FOREIGN KEY (guild_id) REFERENCES antinuke_config(guild_id)
                )
            ''')
            
            self.conn.commit()
        except Exception as e:
            logger.error(f"Database initialization error: {e}")

    def execute(self, query, params=()):
        """Execute a database query"""
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Database execution error: {e}")
            return False

    def fetch_one(self, query, params=()):
        """Fetch a single row from the database"""
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchone()
        except Exception as e:
            logger.error(f"Database fetch error: {e}")
            return None

    def fetch_all(self, query, params=()):
        """Fetch all rows from the database"""
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"Database fetch error: {e}")
            return []

    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()

# Create a global database instance
db = Database() 