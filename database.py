import sqlite3

class Database:
    def __init__(self, db_path):
        """Initialize the database connection."""
        self.db_path = db_path

    def connect(self):
        """Create and return a new database connection."""
        return sqlite3.connect(self.db_path)

    def execute_query(self, query, params=None):
        """Execute a query with optional parameters."""
        params = params or ()
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()

    def fetch_all(self, query, params=None):
        """Fetch all rows for a given query."""
        params = params or ()
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def fetch_one(self, query, params=None):
        """Fetch a single row for a given query."""
        params = params or ()
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()
