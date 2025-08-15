import feedparser
import requests
from newspaper import Article
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsFetcher:
    def __init__(self):
        self.rss_feeds = self._get_rss_feeds()
        self.newsapi_key = os.getenv('NEWSAPI_KEY')
        self.us_sources = {
            'CNN', 'Fox News', 'Reuters', 'New York Times', 'Washington Post',
            'NBC News', 'ABC News', 'NPR', 'New York Post'
        }
    
    def _get_rss_feeds(self) -> List[str]:
        """Get RSS feed URLs from environment variables."""
        feeds_str = os.getenv('RSS_FEEDS', '')
        if feeds_str:
            return [feed.strip() for feed in feeds_str.split(',')]
        # Prioritize US sources first
        us_sources = [
            'https://rss.cnn.com/rss/edition.rss',
            'https://moxie.foxnews.com/google-publisher/latest.xml',
            'https://feeds.reuters.com/reuters/topNews',
            'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',
            'https://feeds.washingtonpost.com/rss/world',
            'https://feeds.nbcnews.com/nbcnews/public/world',
            'https://feeds.abcnews.com/abcnews/internationalheadlines',
            'https://feeds.npr.org/1001/rss.xml',
            'https://nypost.com/feed/',
        ]
        
        international_sources = [
            'https://rss.bbc.co.uk/rss/newsonline_world_edition/front_page/rss.xml',
            'https://www.jpost.com/rss/rssfeedsheadlines.aspx',
            'https://www.tehrantimes.com/rss',
            'https://www.aljazeera.com/xml/rss/all.xml',
            'https://timesofindia.indiatimes.com/rssfeedstopstories.cms',
            'https://www.scmp.com/rss/91/feed',
            'https://www.rt.com/rss/',
            'https://english.alarabiya.net/rss.xml',
        ]
        
        return us_sources + international_sources
    
    def fetch_from_rss(self, feed_url: str) -> List[Dict]:
        """Fetch articles from a single RSS feed."""
        articles = []
        try:
            logger.info(f"Fetching from RSS: {feed_url}")
            
            # Set user agent for better compatibility with international sources
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Parse RSS with headers
            feed = feedparser.parse(feed_url, request_headers=headers)
            
            # Check for feed parsing errors
            if feed.bozo:
                logger.warning(f"RSS feed parsing warning for {feed_url}: {feed.bozo_exception}")
            
            if not feed.entries:
                logger.warning(f"No entries found in RSS feed: {feed_url}")
                return articles
            
            logger.info(f"Found {len(feed.entries)} entries in RSS feed: {feed_url}")
            
            for entry in feed.entries:  # Process all entries from RSS feed
                try:
                    # Extract published date
                    published_at = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published_at = datetime(*entry.published_parsed[:6])
                    
                    # Try to get full article content, but fallback to summary if it fails
                    full_text = entry.get('summary', '')
                    try:
                        article = Article(entry.link)
                        article.download()
                        article.parse()
                        if article.text and len(article.text) > len(full_text):
                            full_text = article.text
                    except Exception as parse_error:
                        logger.warning(f"Could not parse full content for {entry.link}: {str(parse_error)}")
                        # Continue with RSS summary instead of failing
                    
                    article_data = {
                        'title': entry.title,
                        'url': entry.link,
                        'source': self._extract_source_from_url(entry.link),
                        'published_at': published_at,
                        'summary': entry.get('summary', ''),
                        'full_text': full_text,
                        'intent': None,  # Will be filled by AI
                        'emotion': None  # Will be filled by AI
                    }
                    articles.append(article_data)
                    logger.info(f"Successfully processed: {entry.title}")
                    
                except Exception as e:
                    logger.error(f"Error processing article {entry.link}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error fetching RSS feed {feed_url}: {str(e)}")
        
        return articles
    
    def fetch_from_newsapi(self, query: str = "technology", limit: int = 10) -> List[Dict]:
        """Fetch articles from NewsAPI (optional)."""
        if not self.newsapi_key:
            logger.warning("NewsAPI key not found, skipping NewsAPI fetch")
            return []
        
        articles = []
        try:
            url = f"https://newsapi.org/v2/everything"
            params = {
                'q': query,
                'apiKey': self.newsapi_key,
                'sortBy': 'publishedAt',
                'pageSize': limit,
                'language': 'en'
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            for article_data in data.get('articles', []):
                # Parse full article content
                try:
                    article = Article(article_data['url'])
                    article.download()
                    article.parse()
                    full_text = article.text
                except:
                    full_text = article_data.get('content', '')
                
                published_at = None
                if article_data.get('publishedAt'):
                    published_at = datetime.fromisoformat(
                        article_data['publishedAt'].replace('Z', '+00:00')
                    )
                
                processed_article = {
                    'title': article_data['title'],
                    'url': article_data['url'],
                    'source': article_data['source']['name'],
                    'published_at': published_at,
                    'summary': article_data.get('description', ''),
                    'full_text': full_text,
                    'intent': None,
                    'emotion': None
                }
                articles.append(processed_article)
                
        except Exception as e:
            logger.error(f"Error fetching from NewsAPI: {str(e)}")
        
        return articles
    
    def fetch_all_sources(self) -> List[Dict]:
        """Fetch articles from all configured sources with US media prioritization."""
        all_articles = []
        successful_feeds = 0
        failed_feeds = 0
        
        logger.info(f"Starting to fetch from {len(self.rss_feeds)} RSS feeds with US media prioritization")
        
        # Fetch from RSS feeds
        for feed_url in self.rss_feeds:
            try:
                articles = self.fetch_from_rss(feed_url)
                if articles:
                    all_articles.extend(articles)
                    successful_feeds += 1
                    logger.info(f"✓ Successfully fetched {len(articles)} articles from {feed_url}")
                else:
                    failed_feeds += 1
                    logger.warning(f"✗ No articles fetched from {feed_url}")
            except Exception as e:
                failed_feeds += 1
                logger.error(f"✗ Failed to fetch from {feed_url}: {str(e)}")
        
        # Optionally fetch from NewsAPI
        try:
            newsapi_articles = self.fetch_from_newsapi()
            if newsapi_articles:
                all_articles.extend(newsapi_articles)
                logger.info(f"✓ Fetched {len(newsapi_articles)} articles from NewsAPI")
        except Exception as e:
            logger.warning(f"NewsAPI fetch failed: {str(e)}")
        
        # Apply US media prioritization
        prioritized_articles = self._prioritize_us_sources(all_articles)
        
        logger.info(f"Feed summary: {successful_feeds} successful, {failed_feeds} failed")
        logger.info(f"Total articles before prioritization: {len(all_articles)}")
        logger.info(f"Total articles after US prioritization: {len(prioritized_articles)}")
        
        # Group by source for visibility
        sources_count = {}
        for article in prioritized_articles:
            source = article.get('source', 'Unknown')
            sources_count[source] = sources_count.get(source, 0) + 1
        
        logger.info("Articles per source (after US prioritization):")
        us_count = 0
        intl_count = 0
        for source, count in sorted(sources_count.items()):
            is_us = source in self.us_sources
            prefix = "🇺🇸" if is_us else "🌍"
            logger.info(f"  {prefix} {source}: {count} articles")
            if is_us:
                us_count += count
            else:
                intl_count += count
        
        logger.info(f"Summary: {us_count} US articles, {intl_count} international articles")
        
        return prioritized_articles
    
    def _prioritize_us_sources(self, articles: List[Dict], us_limit: int = 12, intl_limit: int = 5) -> List[Dict]:
        """Prioritize US sources by taking up to us_limit articles from each US source and intl_limit from international sources."""
        from collections import defaultdict
        
        # Group articles by source
        articles_by_source = defaultdict(list)
        for article in articles:
            source = article.get('source', 'Unknown')
            articles_by_source[source].append(article)
        
        prioritized_articles = []
        
        # Process US sources first with higher limit
        for source in self.us_sources:
            if source in articles_by_source:
                source_articles = articles_by_source[source][:us_limit]
                prioritized_articles.extend(source_articles)
                logger.info(f"🇺🇸 {source}: Selected {len(source_articles)} articles (US priority)")
        
        # Process international sources with lower limit
        for source, source_articles in articles_by_source.items():
            if source not in self.us_sources:
                limited_articles = source_articles[:intl_limit]
                prioritized_articles.extend(limited_articles)
                logger.info(f"🌍 {source}: Selected {len(limited_articles)} articles (international)")
        
        return prioritized_articles
    
    def _extract_source_from_url(self, url: str) -> str:
        """Extract source name from URL."""
        try:
            domain = url.split('/')[2].lower()
            
            # Define source mappings for better recognition
            source_mappings = {
                'cnn.com': 'CNN',
                'foxnews.com': 'Fox News',
                'moxie.foxnews.com': 'Fox News',
                'reuters.com': 'Reuters',
                'bbc.co.uk': 'BBC',
                'nytimes.com': 'New York Times',
                'washingtonpost.com': 'Washington Post',
                'nbcnews.com': 'NBC News',
                'abcnews.com': 'ABC News',
                'npr.org': 'NPR',
                'nypost.com': 'New York Post',
                'jpost.com': 'Jerusalem Post',
                'tehrantimes.com': 'Tehran Times',
                'aljazeera.com': 'Al Jazeera',
                'timesofindia.indiatimes.com': 'Times of India',
                'scmp.com': 'South China Morning Post',
                'rt.com': 'RT News',
                'alarabiya.net': 'Al Arabiya'
            }
            
            # Check for exact matches
            for key, source_name in source_mappings.items():
                if key in domain:
                    return source_name
            
            # Fallback to domain name cleanup
            clean_domain = domain.replace('www.', '').replace('english.', '')
            return clean_domain.split('.')[0].title()
            
        except Exception as e:
            logger.error(f"Error extracting source from URL {url}: {str(e)}")
            return 'Unknown'