from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
import asyncio
import os
from dotenv import load_dotenv
import logging

from news_fetcher import NewsFetcher
from summarizer import NewsSummarizer
from database import NewsDatabase

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.news_fetcher = NewsFetcher()
        self.summarizer = NewsSummarizer()
        self.database = NewsDatabase()
        self.fetch_interval_hours = int(os.getenv('FETCH_INTERVAL_HOURS', 24))
        self.last_auto_fetch = None
        self.last_manual_fetch = None
    
    async def fetch_and_process_news(self, force: bool = False):
        """Scheduled task to fetch and process news articles."""
        try:
            # Check if we should skip this fetch (only for automatic calls)
            if not force and self.last_auto_fetch:
                time_since_last = datetime.now() - self.last_auto_fetch
                if time_since_last.total_seconds() < (self.fetch_interval_hours * 3600):
                    logger.info(f"Skipping automatic fetch - last fetch was {time_since_last} ago")
                    return
            
            logger.info("Starting news fetch..." + (" (forced)" if force else " (automatic)"))
            
            # Fetch articles from all sources
            articles = self.news_fetcher.fetch_all_sources()
            
            if not articles:
                logger.warning("No articles fetched")
                return
            
            # Filter out articles we already have
            new_articles = []
            for article in articles:
                if not self.database.article_exists(article['url']):
                    new_articles.append(article)
            
            if not new_articles:
                logger.info("No new articles to process")
                return
            
            logger.info(f"Processing {len(new_articles)} new articles...")
            
            # Analyze articles with AI
            analyzed_articles = self.summarizer.batch_analyze_articles(new_articles)
            
            # Store in database
            stored_count = 0
            for article in analyzed_articles:
                try:
                    self.database.insert_article(article)
                    stored_count += 1
                except Exception as e:
                    logger.error(f"Error storing article {article.get('url', '')}: {str(e)}")
            
            logger.info(f"Successfully stored {stored_count} new articles")
            
            # Update last fetch time
            if force:
                self.last_manual_fetch = datetime.now()
            else:
                self.last_auto_fetch = datetime.now()
            
        except Exception as e:
            logger.error(f"Error in news fetch: {str(e)}")
    
    def start_scheduler(self):
        """Start the background scheduler."""
        # Add the scheduled job
        self.scheduler.add_job(
            func=self.fetch_and_process_news,
            trigger=IntervalTrigger(hours=self.fetch_interval_hours),
            id='fetch_news',
            name='Fetch and process news articles',
            replace_existing=True,
            next_run_time=datetime.now()  # Run immediately on start
        )
        
        self.scheduler.start()
        logger.info(f"News scheduler started - will run every {self.fetch_interval_hours} hours")
    
    def stop_scheduler(self):
        """Stop the background scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("News scheduler stopped")
    
    async def manual_fetch(self) -> int:
        """Manually trigger a news fetch (for /update command)."""
        try:
            logger.info("Manual news fetch triggered...")
            await self.fetch_and_process_news(force=True)
            
            # Return count of recent articles
            recent_articles = self.database.get_recent_articles(limit=10)
            return len(recent_articles)
            
        except Exception as e:
            logger.error(f"Error in manual news fetch: {str(e)}")
            return 0
    
    def get_last_fetch_info(self) -> dict:
        """Get information about the last fetch operations."""
        return {
            'last_auto_fetch': self.last_auto_fetch,
            'last_manual_fetch': self.last_manual_fetch,
            'next_auto_fetch': self.last_auto_fetch + timedelta(hours=self.fetch_interval_hours) if self.last_auto_fetch else None
        }