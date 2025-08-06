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
    
    def _get_rss_feeds(self) -> List[str]:
        """Get RSS feed URLs from environment variables."""
        feeds_str = os.getenv('RSS_FEEDS', '')
        if feeds_str:
            return [feed.strip() for feed in feeds_str.split(',')]
        return [
            'https://rss.cnn.com/rss/edition.rss',
            'https://feeds.foxnews.com/foxnews/latest',
            'https://feeds.reuters.com/reuters/topNews'
        ]
    
    def fetch_from_rss(self, feed_url: str) -> List[Dict]:
        """Fetch articles from a single RSS feed."""
        articles = []
        try:
            logger.info(f"Fetching from RSS: {feed_url}")
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:10]:  # Limit to 10 most recent
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
        """Fetch articles from all configured sources."""
        all_articles = []
        
        # Fetch from RSS feeds
        for feed_url in self.rss_feeds:
            articles = self.fetch_from_rss(feed_url)
            all_articles.extend(articles)
        
        # Optionally fetch from NewsAPI
        newsapi_articles = self.fetch_from_newsapi()
        all_articles.extend(newsapi_articles)
        
        logger.info(f"Fetched {len(all_articles)} articles total")
        return all_articles
    
    def _extract_source_from_url(self, url: str) -> str:
        """Extract source name from URL."""
        try:
            domain = url.split('/')[2].lower()
            if 'cnn' in domain:
                return 'CNN'
            elif 'fox' in domain:
                return 'Fox News'
            elif 'reuters' in domain:
                return 'Reuters'
            elif 'bbc' in domain:
                return 'BBC'
            elif 'nytimes' in domain:
                return 'New York Times'
            else:
                return domain.replace('www.', '').title()
        except:
            return 'Unknown'