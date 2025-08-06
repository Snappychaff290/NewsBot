import openai
import os
from typing import Dict, Optional
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsSummarizer:
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = "gpt-4o-mini"  # Cost-effective model for summarization
    
    def analyze_article(self, article_data: Dict) -> Dict:
        """Analyze an article using OpenAI API for summary, intent, and emotion."""
        try:
            # Prepare the content for analysis
            content = f"""
            Title: {article_data.get('title', '')}
            Source: {article_data.get('source', '')}
            Original Summary: {article_data.get('summary', '')}
            Full Text: {article_data.get('full_text', '')[:3000]}
            """
            
            # Create the analysis prompt
            prompt = """
            Please analyze this news article and provide:
            1. A concise 2-3 sentence summary of the key points
            2. The author's intent (inform, persuade, entertain, warn, etc.)
            3. The likely emotional response from readers (neutral, concerned, optimistic, angry, etc.)
            
            Format your response as:
            SUMMARY: [your summary here]
            INTENT: [author's intent]
            EMOTION: [reader emotion target]
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a news analyst that provides objective, concise analysis of news articles."},
                    {"role": "user", "content": f"{prompt}\n\nArticle:\n{content}"}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            analysis_text = response.choices[0].message.content
            return self._parse_analysis(analysis_text, article_data)
            
        except Exception as e:
            logger.error(f"Error analyzing article: {str(e)}")
            return {
                **article_data,
                'summary': article_data.get('summary', 'Summary unavailable'),
                'intent': 'Unknown',
                'emotion': 'Neutral'
            }
    
    def _parse_analysis(self, analysis_text: str, original_article: Dict) -> Dict:
        """Parse the AI analysis response."""
        lines = analysis_text.strip().split('\n')
        
        summary = original_article.get('summary', 'Summary unavailable')
        intent = 'Unknown'
        emotion = 'Neutral'
        
        for line in lines:
            line = line.strip()
            if line.startswith('SUMMARY:'):
                summary = line.replace('SUMMARY:', '').strip()
            elif line.startswith('INTENT:'):
                intent = line.replace('INTENT:', '').strip()
            elif line.startswith('EMOTION:'):
                emotion = line.replace('EMOTION:', '').strip()
        
        return {
            **original_article,
            'summary': summary,
            'intent': intent,
            'emotion': emotion
        }
    
    def batch_analyze_articles(self, articles: list) -> list:
        """Analyze multiple articles in batch."""
        analyzed_articles = []
        
        for i, article in enumerate(articles):
            logger.info(f"Analyzing article {i+1}/{len(articles)}: {article.get('title', 'Untitled')}")
            analyzed_article = self.analyze_article(article)
            analyzed_articles.append(analyzed_article)
        
        return analyzed_articles
    
    def generate_response(self, user_message: str, relevant_articles: list = None, context: str = "") -> str:
        """Generate a conversational response based on user message and relevant articles."""
        try:
            article_context = ""
            if relevant_articles:
                article_context = "Recent news articles that might be relevant:\n\n"
                for article in relevant_articles[:3]:  # Limit to 3 most relevant
                    article_context += f"- {article.get('title', '')}: {article.get('summary', '')}\n"
                article_context += "\n"
            
            full_context = context + article_context if context else article_context
            
            prompt = f"""
            {full_context}You are a friendly, conversational AI news bot. Respond naturally to the user's message.
            
            Guidelines:
            - Act like a knowledgeable friend who stays up-to-date on current events
            - If relevant articles are available, naturally incorporate them into your response
            - If conversation context is provided, reference it naturally
            - Be conversational, not robotic - use natural language
            - You can express opinions but keep them balanced and factual
            - If asked about something you don't have info on, admit it honestly
            - Keep responses engaging but not too long
            
            User message: {user_message}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a friendly, knowledgeable news bot that chats naturally with users about current events. You're helpful, conversational, and provide objective information while being engaging. You can reference recent news articles you have access to."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.8
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "I'm sorry, I'm having trouble processing your request right now. Please try again later!"
    
    def analyze_news_collection(self, articles: list) -> str:
        """Analyze a collection of articles for unbiased summary and intent analysis."""
        try:
            # Prepare articles for analysis
            articles_text = ""
            for i, article in enumerate(articles[:10], 1):  # Limit to 10 articles
                articles_text += f"\n{i}. **{article.get('source', 'Unknown')}** - {article.get('title', '')}\n"
                articles_text += f"Summary: {article.get('summary', 'No summary available')}\n"
                if article.get('published_at'):
                    articles_text += f"Published: {article.get('published_at')}\n"
                articles_text += f"URL: {article.get('url', '')}\n\n"
            
            prompt = f"""
            Analyze these recent news articles and provide:
            1. A balanced, factual overview of the main topics covered
            2. Key themes and trends across the articles
            3. Any significant events or developments
            4. Author intents (inform, persuade, alert, etc.) where discernible
            
            Be completely objective and avoid any political bias. Present facts and let readers form their own opinions.
            Keep the analysis concise but comprehensive.
            
            Articles to analyze:
            {articles_text}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an objective news analyst. Provide factual, unbiased analysis without political correctness or partisan viewpoints. Present information neutrally and let readers form their own conclusions."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.3  # Lower temperature for more factual, consistent analysis
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error analyzing news collection: {str(e)}")
            return "I'm sorry, I encountered an error while analyzing the news articles."