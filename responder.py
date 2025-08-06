import re
from typing import List, Dict, Optional
import logging

from database import NewsDatabase
from summarizer import NewsSummarizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConversationalResponder:
    def __init__(self):
        self.database = NewsDatabase()
        self.summarizer = NewsSummarizer()
        
        # Keywords that might indicate news-related queries
        self.news_keywords = [
            'news', 'article', 'story', 'report', 'breaking', 'latest',
            'politics', 'technology', 'economy', 'sports', 'health',
            'science', 'business', 'entertainment', 'world', 'local'
        ]
    
    def is_news_related(self, message: str) -> bool:
        """Check if a message is likely news-related."""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in self.news_keywords)
    
    def extract_search_terms(self, message: str) -> List[str]:
        """Extract potential search terms from a message."""
        # Remove common stop words and extract meaningful terms
        stop_words = {'what', 'is', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        
        # Simple tokenization and cleaning
        words = re.findall(r'\b\w+\b', message.lower())
        search_terms = [word for word in words if word not in stop_words and len(word) > 2]
        
        return search_terms[:5]  # Limit to top 5 terms
    
    async def handle_mention(self, message: str, user_name: str = None, recent_messages: list = None) -> str:
        """Handle when the bot is mentioned in a message."""
        try:
            logger.info(f"Processing mention from {user_name}: {message}")
            
            # Build context from recent messages if provided
            context = ""
            if recent_messages:
                context = "Recent conversation context:\n"
                for msg in recent_messages[-5:]:  # Last 5 messages for context
                    context += f"{msg.get('author', 'User')}: {msg.get('content', '')}\n"
                context += "\n"
            
            # Always try to find relevant articles first, regardless of whether it seems "news-related"
            search_terms = self.extract_search_terms(message)
            relevant_articles = []
            
            if search_terms:
                for term in search_terms:
                    articles = self.database.search_articles(term, limit=2)
                    relevant_articles.extend(articles)
                
                # Remove duplicates while preserving order
                seen_urls = set()
                unique_articles = []
                for article in relevant_articles:
                    if article['url'] not in seen_urls:
                        unique_articles.append(article)
                        seen_urls.add(article['url'])
                
                # Use the unique articles for context
                relevant_articles = unique_articles[:3]
            
            # If no relevant articles but the query seems news-related, get recent articles
            if not relevant_articles and self.is_news_related(message):
                relevant_articles = self.database.get_recent_articles(limit=3)
            
            # Generate conversational response with all available context
            ai_response = self.summarizer.generate_response(message, relevant_articles, context)
            return ai_response
                
        except Exception as e:
            logger.error(f"Error handling mention: {str(e)}")
            return "I'm sorry, I'm having trouble processing your request right now. Please try again later!"
    
    async def _handle_news_query(self, message: str, context: str = "") -> str:
        """Handle news-related queries."""
        search_terms = self.extract_search_terms(message)
        
        if not search_terms:
            # Return recent news if no specific search terms
            recent_articles = self.database.get_recent_articles(limit=3)
            if recent_articles:
                response = "Here are the latest news articles I have:\n\n"
                for article in recent_articles:
                    response += f"📰 **{article['source']}** - {article['title']}\n"
                    response += f"🔗 {article['url']}\n"
                    if article.get('summary'):
                        response += f"📝 {article['summary']}\n"
                    response += "\n"
                return response
            else:
                return "I don't have any recent news articles yet. Try running `|update` to fetch the latest articles!"
        
        # Search for relevant articles
        relevant_articles = []
        for term in search_terms:
            articles = self.database.search_articles(term, limit=2)
            relevant_articles.extend(articles)
        
        # Remove duplicates while preserving order
        seen_urls = set()
        unique_articles = []
        for article in relevant_articles:
            if article['url'] not in seen_urls:
                unique_articles.append(article)
                seen_urls.add(article['url'])
        
        if unique_articles:
            # Use AI to generate a contextual response
            ai_response = self.summarizer.generate_response(message, unique_articles[:3], context)
            
            response = f"{ai_response}\n\n**Related Articles:**\n"
            for article in unique_articles[:3]:
                response += f"📰 **{article['source']}** - {article['title']}\n"
                response += f"🔗 {article['url']}\n\n"
            
            return response
        else:
            # No relevant articles found
            return f"I couldn't find any articles related to your query about '{' '.join(search_terms)}'. Try running `|update` to fetch the latest articles, or ask me about something else!"
    
    async def _handle_general_query(self, message: str, context: str = "") -> str:
        """Handle general non-news queries."""
        # Generate AI response for general queries with context
        try:
            ai_response = self.summarizer.generate_response(message, context=context)
            return ai_response
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return "I'm here to help with news and information! Try asking me about recent news or use `|news` to get the latest articles."
    
    def _get_help_response(self) -> str:
        """Return a help message about the bot's capabilities."""
        return """I can help you with:
• 📰 Get AI analysis of latest news with `|news`
• 🔄 Fetch new articles manually with `|update`
• 🏢 List news sources with `|sources`
• 📊 View bot statistics with `|stats`
• 💬 Answer questions about recent news when mentioned
• 🔍 Search for articles on specific topics

**Commands:**
• `|news [source]` - AI analysis of recent articles
• `|update` - Manually fetch latest news (bypasses 24hr limit)
• `|sources` - List available news sources
• `|stats` - Show bot statistics
• `|help` - Show this help message

**Mention Features:**
Just mention me with your question, and I'll use recent conversation context and stored articles to help!

Examples:
- "What's the latest on technology?"
- "Any news about climate change?"
- "Tell me about recent political developments"

I automatically fetch news every 24 hours, but you can force an update anytime with `|update`."""
    
    def get_database_info(self) -> str:
        """Get information about the current database state."""
        try:
            stats = self.database.get_database_stats()
            return f"""📊 **Database Stats**
• Total Articles: {stats['total_articles']}
• Unique Sources: {stats['unique_sources']}
• Last Update: {stats['latest_update'] or 'Never'}

Recent articles available for search and discussion!"""
        except Exception as e:
            logger.error(f"Error getting database info: {str(e)}")
            return "Unable to retrieve database information at the moment."