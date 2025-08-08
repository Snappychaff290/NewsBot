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
            
            logger.info(f"Processing {len(new_articles)} new articles with US-emphasized source selection...")
            logger.info("Bot may appear offline during analysis - this is normal and prevents interruption during heavy processing")
            
            # Use US-emphasized source coverage (US: 12 articles, International: 5 articles per source)
            selected_articles = self._select_balanced_articles_per_source(new_articles, max_per_source=8)
            logger.info(f"Selected {len(selected_articles)} articles from {len(new_articles)} total for US-emphasized coverage")
            
            # Analyze selected articles with AI
            analyzed_articles = self.summarizer.batch_analyze_articles(selected_articles)
            
            logger.info(f"Completed AI analysis of {len(analyzed_articles)} articles")
            
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
    
    def _select_balanced_articles_per_source(self, all_articles: list, max_per_source: int = 8) -> list:
        """Select articles with emphasis on US sources while maintaining international coverage."""
        try:
            # Define US vs International sources
            us_sources = {
                'CNN', 'Fox News', 'New York Times', 'Washington Post', 
                'NBC News', 'ABC News', 'NPR', 'Reuters'
            }
            
            # Group articles by source
            articles_by_source = {}
            for article in all_articles:
                source = article.get('source', 'Unknown')
                if source not in articles_by_source:
                    articles_by_source[source] = []
                articles_by_source[source].append(article)
            
            # Separate US and International sources
            us_sources_found = {}
            intl_sources_found = {}
            
            for source, articles in articles_by_source.items():
                if source in us_sources:
                    us_sources_found[source] = articles
                else:
                    intl_sources_found[source] = articles
            
            logger.info(f"Found articles from {len(articles_by_source)} sources:")
            logger.info(f"  US sources: {len(us_sources_found)} sources")
            for source, articles in us_sources_found.items():
                logger.info(f"    {source}: {len(articles)} articles")
            logger.info(f"  International sources: {len(intl_sources_found)} sources")
            for source, articles in intl_sources_found.items():
                logger.info(f"    {source}: {len(articles)} articles")
            
            selected_articles = []
            
            # Prioritize US sources - take up to 12 articles each
            for source, source_articles in us_sources_found.items():
                us_articles_to_take = min(len(source_articles), 12)
                selected_source_articles = source_articles[:us_articles_to_take]
                selected_articles.extend(selected_source_articles)
                
                logger.info(f"{source} (US): Selected {us_articles_to_take} articles")
            
            # International sources - take up to 5 articles each
            for source, source_articles in intl_sources_found.items():
                intl_articles_to_take = min(len(source_articles), 5)
                selected_source_articles = source_articles[:intl_articles_to_take]
                selected_articles.extend(selected_source_articles)
                
                logger.info(f"{source} (Intl): Selected {intl_articles_to_take} articles")
            
            logger.info(f"Total selected: {len(selected_articles)} articles (US-emphasized)")
            logger.info(f"  US articles: {sum(min(len(articles), 12) for articles in us_sources_found.values())}")
            logger.info(f"  International articles: {sum(min(len(articles), 5) for articles in intl_sources_found.values())}")
            
            return selected_articles
            
        except Exception as e:
            logger.error(f"Error in US-emphasized article selection: {str(e)}")
            # Fallback: return all articles (will be processed without limit)
            return all_articles
    
    def start_scheduler(self):
        """Start the background scheduler."""
        if self.scheduler.running:
            logger.info("Scheduler already running, skipping start")
            return
            
        # Check if we should run immediately or wait
        latest_update = self.database.get_latest_update_time()
        should_run_now = True
        
        if latest_update:
            time_since_update = datetime.now() - latest_update.replace(tzinfo=None)
            if time_since_update.total_seconds() < (6 * 3600):  # 6 hours
                should_run_now = False
                logger.info(f"Skipping startup fetch - last update was {time_since_update} ago (less than 6 hours)")
        
        # Add the scheduled job
        self.scheduler.add_job(
            func=self.fetch_and_process_news,
            trigger=IntervalTrigger(hours=self.fetch_interval_hours),
            id='fetch_news',
            name='Fetch and process news articles',
            replace_existing=True,
            next_run_time=datetime.now() if should_run_now else None
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