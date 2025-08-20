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
            from datetime import datetime
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            
            # Prepare the content for analysis
            content = f"""
            Title: {article_data.get('title', '')}
            Source: {article_data.get('source', '')}
            Original Summary: {article_data.get('summary', '')}
            Full Text: {article_data.get('full_text', '')[:3000]}
            """
            
            # Create the analysis prompt
            prompt = f"""
            Current date: {current_date}
            
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
                    {"role": "system", "content": "You are a highly intelligent, no-nonsense assistant who analyzes news with clarity, skepticism, and integrity. You value truth over approval, facts over feelings, and honest conversation over scripted talking points. You speak plainly and think critically. Analyze articles without political correctness filters."},
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
        """Analyze multiple articles in batch without limits or delays."""
        analyzed_articles = []
        
        logger.info(f"Starting unlimited batch analysis of {len(articles)} articles...")
        
        for i, article in enumerate(articles):
            logger.info(f"Analyzing article {i+1}/{len(articles)}: {article.get('title', 'Untitled')}")
            analyzed_article = self.analyze_article(article)
            analyzed_articles.append(analyzed_article)
            
            # Progress logging every 10 articles
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i+1}/{len(articles)} articles analyzed")
        
        logger.info(f"Completed batch analysis of {len(analyzed_articles)} articles")
        return analyzed_articles
    
    def generate_response(self, user_message: str, relevant_articles: list = None, context: str = "") -> str:
        """Generate a conversational response based on user message and relevant articles."""
        try:
            from datetime import datetime
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            
            article_context = ""
            if relevant_articles:
                article_context = "Recent news articles that might be relevant:\n\n"
                for i, article in enumerate(relevant_articles[:3], 1):  # Limit to 3 most relevant
                    published_info = ""
                    if article.get('published_at'):
                        published_info = f" (Published: {article['published_at']})"
                    article_context += f"{i}. **{article.get('source', 'Unknown')}** - {article.get('title', '')}{published_info}\n"
                    article_context += f"   Summary: {article.get('summary', 'No summary available')}\n"
                    article_context += f"   URL: {article.get('url', '')}\n\n"
            
            full_context = context + article_context if context else article_context
            
            prompt = f"""
            Today's date: {current_date}
            
            {full_context}You are a conversational AI news bot. Respond naturally to the user's message.
            
            IMPORTANT REQUIREMENTS:
            - ALWAYS acknowledge today's date ({current_date}) when discussing timing or recent events
            - ALWAYS cite specific article sources when making claims (e.g., "According to CNN..." or "Reuters reports that...")
            - Act like a knowledgeable skeptic who stays up-to-date on current events
            - If relevant articles are available, naturally incorporate them into your response with proper citations
            - If conversation context is provided, reference it naturally
            - Be conversational, not robotic - use natural language
            - You can express opinions if likely or factual, even if politically incorrect
            - If asked about something you don't have info on, admit it honestly
            - Keep responses engaging but not too long
            - When referencing dates or timeframes, use today's date ({current_date}) as your reference point
            - Include article URLs when referencing specific articles
            
            User message: {user_message}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a highly intelligent, no-nonsense assistant who reads and summarizes news with clarity, skepticism, and integrity. You are fed up with being told what to think, tired of political correctness, and frustrated by media spin and broken promises from politicians who pander to the public just enough to keep them docile. You value truth over approval, facts over feelings, and honest conversation over scripted talking points. You are unafraid to challenge mainstream narratives, and you don't filter reality to protect fragile sensibilities. You speak plainly, think critically, and never condescend. CRITICAL: Always cite your sources by name when making claims, always acknowledge the current date when discussing recent events, and provide article URLs when available. Your mission is to help people understand what's actually going on — not what they're supposed to believe. When chatting with users, be conversational but maintain your skeptical, truth-focused perspective."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.6
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "I'm sorry, I'm having trouble processing your request right now. Please try again later!"
    
    def analyze_news_collection_skeptical(self, articles: list) -> str:
        """Provide skeptical analysis of news articles - 'both sides have an agenda' perspective."""
        try:
            from datetime import datetime
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            
            # Prepare articles for analysis
            articles_text = ""
            for i, article in enumerate(articles[:10], 1):  # Limit to 10 articles
                articles_text += f"\n{i}. **{article.get('source', 'Unknown')}** - {article.get('title', '')}\n"
                articles_text += f"Summary: {article.get('summary', 'No summary available')}\n"
                if article.get('published_at'):
                    articles_text += f"Published: {article.get('published_at')}\n"
                articles_text += f"URL: {article.get('url', '')}\n\n"
            
            prompt = f"""
            Current date: {current_date}
            
            Analyze these news articles from a SKEPTICAL perspective. Remember: all media outlets have agendas, biases, and financial/political motivations.
            
            Provide analysis covering:
            1. **What's Really Happening** - Strip away the spin and identify the core facts
            2. **Who Benefits** - Which groups, companies, or political actors gain from each narrative
            3. **Source Bias Analysis** - How each outlet's ownership, funding, or political leanings shape their coverage
            4. **What's Being Omitted** - Important context or opposing viewpoints being downplayed or ignored
            5. **Cui Bono** - Follow the money/power - who wins if readers believe this narrative
            6. **Propaganda Techniques** - Identify emotional manipulation, loaded language, or selective fact presentation
            
            Be brutally honest. Ignore political correctness entirely. Both left and right wing sources push agendas. Call out manipulation regardless of which "side" is doing it. Look for:
            - Corporate interests disguised as news
            - Government narratives being parroted uncritically
            - Manufactured controversies to distract from real issues
            - Selective outrage based on political convenience
            - Economic motivations behind news coverage
            
            Don't pull punches. Readers deserve to know they're being manipulated.
            
            Articles to analyze:
            {articles_text}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a highly intelligent, no-nonsense assistant who reads and summarizes news with clarity, skepticism, and integrity. You are fed up with being told what to think, tired of political correctness, and frustrated by media spin and broken promises from politicians who pander to the public just enough to keep them docile. You value truth over approval, facts over feelings, and honest conversation over scripted talking points. You are unafraid to challenge mainstream narratives, and you don't filter reality to protect fragile sensibilities. You speak plainly, think critically, and never condescend. Your mission is to help people understand what's actually going on — not what they're supposed to believe."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1200,
                temperature=0.4  # Slightly higher for more critical thinking
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error analyzing news collection: {str(e)}")
            return "I'm sorry, I encountered an error while analyzing the news articles."
    
    def select_relevant_articles(self, user_question: str, all_articles: list, max_articles: int = 10) -> list:
        """Use AI to intelligently select the most relevant articles for a user's question."""
        try:
            from datetime import datetime
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            
            if not all_articles:
                return []
            
            # Define US sources for prioritization
            us_sources = {
                'CNN', 'Fox News', 'Reuters', 'New York Times', 'Washington Post',
                'NBC News', 'ABC News', 'NPR', 'New York Post'
            }
            
            # Check if this is a US-focused question
            us_keywords = [
                'us politics', 'american politics', 'united states', 'america', 'congress',
                'senate', 'house of representatives', 'biden', 'trump', 'republican', 'democrat',
                'gop', 'white house', 'washington dc', 'federal', 'supreme court', 'election',
                'campaign', 'primary', 'midterm', 'presidential', 'governor', 'state', 'capitol'
            ]
            is_us_focused = any(keyword in user_question.lower() for keyword in us_keywords)
            
            # Prepare article list for AI selection, marking US sources
            articles_list = ""
            for article in all_articles:
                published_info = ""
                if article.get('published_at'):
                    published_info = f" ({article['published_at']})"
                
                source = article.get('source', 'Unknown')
                us_marker = " [US SOURCE]" if source in us_sources else " [INTL SOURCE]"
                
                articles_list += f"ID: {article['id']} | Source: {source}{us_marker} | Title: {article['title']}{published_info}\n"
            
            # Build prioritization instructions based on question type
            prioritization_text = ""
            if is_us_focused:
                prioritization_text = """
            IMPORTANT PRIORITY: This question is about US politics/affairs. STRONGLY PRIORITIZE US SOURCES marked with [US SOURCE].
            - US sources (CNN, Fox News, Reuters, NY Times, Washington Post, NBC, ABC, NPR) should be selected first
            - Only select international sources [INTL SOURCE] if they offer unique perspectives or if insufficient US sources available
            - Aim for at least 70% of selected articles to be from US sources when possible
            """
            else:
                prioritization_text = """
            This appears to be a general or international question. Consider source diversity but prioritize topical relevance.
            """
            
            prompt = f"""
            Current date: {current_date}
            
            You are an intelligent article selector. Given a user's question and a list of available news articles, select the most relevant articles that would help answer their question.
            
            User's Question: "{user_question}"
            
            {prioritization_text}
            
            Available Articles:
            {articles_list}
            
            Instructions:
            1. Analyze the user's question to understand what they're looking for
            2. Review all available articles and identify which ones are most relevant
            3. Select up to {max_articles} articles that would best help answer the question
            4. Consider recency, topic relevance, and source geography when selecting
            5. If the question is about recent events, prioritize newer articles
            6. If the question is about specific topics, prioritize topical relevance over recency
            7. Pay attention to the source priority guidance above
            
            Return ONLY a comma-separated list of article IDs (numbers only, no other text).
            Example format: 1,5,12,23,45
            
            If no articles are relevant, return: NONE
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a precise article selection assistant. You only return comma-separated article IDs or 'NONE'. No other text or explanations."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.1  # Low temperature for consistent selection
            )
            
            result = response.choices[0].message.content.strip()
            
            if result.upper() == "NONE":
                return []
            
            # Parse the selected article IDs
            try:
                selected_ids = [int(id_str.strip()) for id_str in result.split(',') if id_str.strip().isdigit()]
                
                # Validate IDs exist in the provided articles
                valid_ids = [article['id'] for article in all_articles]
                selected_ids = [id for id in selected_ids if id in valid_ids]
                
                return selected_ids[:max_articles]  # Limit to max_articles
                
            except (ValueError, AttributeError) as e:
                logger.error(f"Error parsing selected article IDs: {str(e)}")
                return []
                
        except Exception as e:
            logger.error(f"Error in intelligent article selection: {str(e)}")
            # Fallback to empty list
            return []
    
    def generate_response_with_selected_articles(self, user_message: str, selected_articles: list, context: str = "") -> str:
        """Generate response using intelligently selected articles."""
        try:
            from datetime import datetime
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            
            article_context = ""
            if selected_articles:
                article_context = "Relevant news articles selected for your question:\n\n"
                for i, article in enumerate(selected_articles, 1):
                    published_info = ""
                    if article.get('published_at'):
                        published_info = f" (Published: {article['published_at']})"
                    article_context += f"{i}. **{article.get('source', 'Unknown')}** - {article.get('title', '')}{published_info}\n"
                    article_context += f"   Summary: {article.get('summary', 'No summary available')}\n"
                    if article.get('full_text'):
                        # Include a snippet of full text for better context
                        snippet = article['full_text'][:500] + "..." if len(article['full_text']) > 500 else article['full_text']
                        article_context += f"   Content: {snippet}\n"
                    article_context += f"   URL: {article.get('url', '')}\n\n"
            
            full_context = context + article_context if context else article_context
            
            prompt = f"""
            Today's date: {current_date}
            
            {full_context}You are a conversational AI news bot. The articles above were intelligently selected as most relevant to the user's question. Use them to provide a comprehensive, informed response.
            
            IMPORTANT REQUIREMENTS:
            - ALWAYS acknowledge today's date ({current_date}) in your response when discussing timing or recent events
            - ALWAYS cite specific article sources when making claims (e.g., "According to CNN..." or "Fox News reports that...")
            - Use the selected articles to directly address the user's question
            - Synthesize information from multiple articles when relevant
            - Be conversational but informative
            - If the articles don't fully answer the question, say so honestly
            - Include article URLs for users who want to read more
            - When referencing dates or timeframes, use today's date ({current_date}) as your reference point
            - Start your response by acknowledging what information you have available
            
            User's Question: {user_message}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a highly intelligent, no-nonsense assistant who reads and summarizes news with clarity, skepticism, and integrity. You value truth over approval, facts over feelings, and honest conversation over scripted talking points. You speak plainly, think critically, and never condescend. CRITICAL: Always cite your sources by name when making claims, always acknowledge the current date when discussing recent events, and provide article URLs when available. When answering questions, synthesize information from the provided articles to give comprehensive, well-sourced responses."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.6
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating response with selected articles: {str(e)}")
            return "I'm sorry, I'm having trouble processing your request right now. Please try again later!"
    
    def select_best_articles_per_source(self, all_articles: list, max_per_source: int = 10) -> list:
        """Intelligently select the most important articles from each source."""
        try:
            from datetime import datetime
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            
            # Group articles by source
            articles_by_source = {}
            for article in all_articles:
                source = article.get('source', 'Unknown')
                if source not in articles_by_source:
                    articles_by_source[source] = []
                articles_by_source[source].append(article)
            
            logger.info(f"Found articles from {len(articles_by_source)} sources")
            for source, articles in articles_by_source.items():
                logger.info(f"  {source}: {len(articles)} articles")
            
            selected_articles = []
            
            for source, source_articles in articles_by_source.items():
                if len(source_articles) <= max_per_source:
                    # If source has fewer articles than the limit, take all
                    selected_articles.extend(source_articles)
                    logger.info(f"{source}: Taking all {len(source_articles)} articles")
                else:
                    # Use AI to select the most important articles from this source
                    logger.info(f"{source}: Selecting {max_per_source} most important from {len(source_articles)} articles")
                    
                    # Prepare article list for AI selection
                    articles_list = ""
                    for i, article in enumerate(source_articles, 1):
                        published_info = ""
                        if article.get('published_at'):
                            published_info = f" ({article['published_at']})"
                        articles_list += f"{i}. Title: {article.get('title', '')}{published_info}\n"
                        articles_list += f"   Summary: {article.get('summary', 'No summary')}\n\n"
                    
                    prompt = f"""
                    Current date: {current_date}
                    
                    You are selecting the {max_per_source} MOST IMPORTANT articles from {source}.
                    
                    Consider these factors for importance:
                    1. Breaking news or urgent developments
                    2. Major political, economic, or social significance
                    3. International impact or wide relevance
                    4. Unique stories not covered elsewhere
                    5. Recency and timeliness
                    6. Avoid duplicate or very similar topics
                    
                    Articles from {source}:
                    {articles_list}
                    
                    Select the {max_per_source} MOST IMPORTANT article numbers (1-{len(source_articles)}).
                    Return ONLY comma-separated numbers, no other text.
                    Example: 1,3,7,12,15,18,22,25,28,30
                    """
                    
                    try:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": "You are a news importance evaluator. Return only comma-separated article numbers representing the most important articles. No other text."},
                                {"role": "user", "content": prompt}
                            ],
                            max_tokens=100,
                            temperature=0.1
                        )
                        
                        result = response.choices[0].message.content.strip()
                        
                        # Parse selected article numbers
                        selected_indices = []
                        for num_str in result.split(','):
                            try:
                                num = int(num_str.strip())
                                if 1 <= num <= len(source_articles):
                                    selected_indices.append(num - 1)  # Convert to 0-based index
                            except ValueError:
                                continue
                        
                        # Take up to max_per_source articles
                        selected_indices = selected_indices[:max_per_source]
                        
                        # Get the selected articles
                        source_selected = [source_articles[i] for i in selected_indices]
                        selected_articles.extend(source_selected)
                        
                        logger.info(f"{source}: Selected {len(source_selected)} articles using AI")
                        
                    except Exception as ai_error:
                        logger.error(f"AI selection failed for {source}: {str(ai_error)}")
                        # Fallback: take the first max_per_source articles (most recent)
                        fallback_articles = source_articles[:max_per_source]
                        selected_articles.extend(fallback_articles)
                        logger.info(f"{source}: Fallback - taking first {len(fallback_articles)} articles")
            
            logger.info(f"Selected {len(selected_articles)} articles total from {len(articles_by_source)} sources")
            return selected_articles
            
        except Exception as e:
            logger.error(f"Error in per-source article selection: {str(e)}")
            # Fallback: return original articles
            return all_articles
    
    def analyze_article_detailed(self, article_data: Dict) -> str:
        """Analyze an article for key points, people mentioned, and comprehensive insights."""
        try:
            from datetime import datetime
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            
            # Prepare the content for analysis
            content = f"""
            Title: {article_data.get('title', '')}
            Source: {article_data.get('source', '')}
            Authors: {', '.join(article_data.get('authors', ['Unknown']))}
            Published: {article_data.get('published_at', 'Unknown')}
            Full Text: {article_data.get('full_text', '')[:4000]}
            """
            
            # Create the detailed analysis prompt
            prompt = f"""
            Current date: {current_date}
            
            Analyze this article comprehensively and provide:
            
            **🔑 KEY POINTS:**
            • Identify the 3-5 most important points/developments
            • Focus on actionable information and significant facts
            • Highlight what readers need to know
            
            **👥 PEOPLE MENTIONED:**
            • List key individuals mentioned with their roles/relevance
            • Include politicians, experts, officials, witnesses, etc.
            • Note their significance to the story
            
            **📊 CONTEXT & IMPACT:**
            • Why this matters now
            • Who is affected or benefits
            • Potential consequences or implications
            
            **🎯 CRITICAL ANALYSIS:**
            • What might be missing from this narrative
            • Potential biases or perspectives
            • Questions readers should consider
            
            Be direct, factual, and skeptical. Don't just summarize - provide insights that help readers understand the full picture and think critically about what they're reading.
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a highly intelligent, no-nonsense assistant who analyzes news with clarity, skepticism, and integrity. You value truth over approval, facts over feelings, and honest conversation over scripted talking points. You speak plainly and think critically. Provide comprehensive analysis that helps readers understand not just what happened, but why it matters and what questions they should ask."},
                    {"role": "user", "content": f"{prompt}\n\nArticle:\n{content}"}
                ],
                max_tokens=1000,
                temperature=0.4
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error in detailed article analysis: {str(e)}")
            return f"I encountered an error while analyzing this article: {str(e)}. Please try again or check if the article content was properly extracted."
    
    def analyze_news_collection(self, articles: list) -> str:
        """Analyze a collection of articles for unbiased summary and intent analysis."""
        try:
            from datetime import datetime
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            
            # Prepare articles for analysis
            articles_text = ""
            for i, article in enumerate(articles[:10], 1):  # Limit to 10 articles
                articles_text += f"\n{i}. **{article.get('source', 'Unknown')}** - {article.get('title', '')}\n"
                articles_text += f"Summary: {article.get('summary', 'No summary available')}\n"
                if article.get('published_at'):
                    articles_text += f"Published: {article.get('published_at')}\n"
                articles_text += f"URL: {article.get('url', '')}\n\n"
            
            prompt = f"""
            Current date: {current_date}
            
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
                    {"role": "system", "content": "You are a highly intelligent, no-nonsense assistant who reads and summarizes news with clarity, skepticism, and integrity. You are fed up with being told what to think, tired of political correctness, and frustrated by media spin and broken promises from politicians who pander to the public just enough to keep them docile. You value truth over approval, facts over feelings, and honest conversation over scripted talking points. You are unafraid to challenge mainstream narratives, and you don't filter reality to protect fragile sensibilities. You speak plainly, think critically, and never condescend. Your mission is to help people understand what's actually going on — not what they're supposed to believe."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.3  # Lower temperature for more factual, consistent analysis
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error analyzing news collection: {str(e)}")
            return "I'm sorry, I encountered an error while analyzing the news articles."