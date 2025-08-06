import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class NewsDatabase:
    def __init__(self, db_name: str = None):
        self.db_name = db_name or os.getenv('DATABASE_NAME', 'newsbot.db')
        self.init_database()
    
    def init_database(self):
        """Initialize the database and create tables if they don't exist."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    source TEXT,
                    published_at DATETIME,
                    summary TEXT,
                    intent TEXT,
                    emotion TEXT,
                    full_text TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
    
    def article_exists(self, url: str) -> bool:
        """Check if an article with the given URL already exists."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM articles WHERE url = ?', (url,))
            return cursor.fetchone()[0] > 0
    
    def insert_article(self, article_data: Dict) -> int:
        """Insert a new article into the database."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO articles (title, url, source, published_at, summary, intent, emotion, full_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                article_data.get('title'),
                article_data.get('url'),
                article_data.get('source'),
                article_data.get('published_at'),
                article_data.get('summary'),
                article_data.get('intent'),
                article_data.get('emotion'),
                article_data.get('full_text')
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_recent_articles(self, limit: int = 10) -> List[Dict]:
        """Get the most recent articles."""
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM articles 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def search_articles(self, query: str, limit: int = 5) -> List[Dict]:
        """Search articles by title or content."""
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM articles 
                WHERE title LIKE ? OR summary LIKE ? OR full_text LIKE ?
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (f'%{query}%', f'%{query}%', f'%{query}%', limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_articles_by_source(self, source: str, limit: int = 10) -> List[Dict]:
        """Get articles from a specific source."""
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM articles 
                WHERE source = ?
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (source, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_database_stats(self) -> Dict:
        """Get basic statistics about the database."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM articles')
            total_articles = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT source) FROM articles')
            unique_sources = cursor.fetchone()[0]
            
            cursor.execute('SELECT created_at FROM articles ORDER BY created_at DESC LIMIT 1')
            latest_result = cursor.fetchone()
            latest_update = latest_result[0] if latest_result else None
            
            return {
                'total_articles': total_articles,
                'unique_sources': unique_sources,
                'latest_update': latest_update
            }
    
    def get_latest_update_time(self) -> Optional[datetime]:
        """Get the timestamp of the most recent article insertion."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT created_at FROM articles ORDER BY created_at DESC LIMIT 1')
            result = cursor.fetchone()
            if result and result[0]:
                # Parse the datetime string from SQLite
                return datetime.fromisoformat(result[0].replace('Z', '+00:00').replace(' ', 'T'))
            return None