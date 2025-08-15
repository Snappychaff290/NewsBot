import discord
from discord.ext import commands
import os
import asyncio
import logging
from dotenv import load_dotenv

from database import NewsDatabase
from news_fetcher import NewsFetcher
from summarizer import NewsSummarizer
from scheduler import NewsScheduler
from responder import ConversationalResponder

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='|', intents=intents, help_command=None)

# Initialize components
database = NewsDatabase()
news_fetcher = NewsFetcher()
summarizer = NewsSummarizer()
scheduler = NewsScheduler()
responder = ConversationalResponder()

# Store pending article selections
pending_selections = {}

# Clean up old selections periodically
import asyncio
from datetime import datetime, timedelta

async def cleanup_old_selections():
    """Clean up selections older than 5 minutes."""
    while True:
        try:
            current_time = datetime.now()
            expired_keys = []
            for key, data in pending_selections.items():
                if 'timestamp' in data:
                    if current_time - data['timestamp'] > timedelta(minutes=5):
                        expired_keys.append(key)
            
            for key in expired_keys:
                del pending_selections[key]
                
        except Exception as e:
            logger.error(f"Error cleaning up selections: {str(e)}")
        
        await asyncio.sleep(300)  # Check every 5 minutes

@bot.event
async def on_ready():
    """Called when the bot is ready."""
    logger.info(f'{bot.user} has connected to Discord!')
    
    # Start the news scheduler
    scheduler.start_scheduler()
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="🔍 through media BS & propaganda"
        )
    )
    
    print(f"🔍 No-BS News Analyst is online!")
    print(f"📊 Database: {database.get_database_stats()['total_articles']} articles stored")
    print(f"💥 Ready to cut through propaganda and expose the truth!")
    
    # Start cleanup task
    asyncio.create_task(cleanup_old_selections())

@bot.event
async def on_message(message):
    """Handle incoming messages."""
    # Ignore bot's own messages
    if message.author == bot.user:
        return
    
    # Check if bot is mentioned
    if bot.user.mentioned_in(message) and not message.mention_everyone:
        # Remove the bot mention from the message
        content = message.content.replace(f'<@{bot.user.id}>', '').strip()
        if not content:
            content = "Hello!"
        
        # Get recent messages for context (last 5 messages)
        recent_messages = []
        try:
            async for msg in message.channel.history(limit=6, before=message):
                if msg.author != bot.user:  # Skip bot messages for context
                    recent_messages.append({
                        'author': msg.author.display_name,
                        'content': msg.content[:200]  # Limit content length
                    })
        except Exception as e:
            logger.error(f"Error fetching message history: {str(e)}")
        
        # Generate response with context
        response = await responder.handle_mention(content, message.author.display_name, recent_messages)
        
        # Send response
        if len(response) > 2000:
            # Split long messages
            chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
            for chunk in chunks:
                await message.channel.send(chunk)
        else:
            await message.channel.send(response)
    
    # Process commands
    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    """Handle reaction-based article selection with confirmation."""
    # Ignore bot's own reactions
    if user == bot.user:
        return
    
    # Check if this is a pending selection
    selection_key = f"{reaction.message.channel.id}_{reaction.message.id}_{user.id}"
    if selection_key not in pending_selections:
        return
    
    selection_data = pending_selections[selection_key]
    
    # Process the reaction
    number_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
    
    try:
        if reaction.emoji == '✅':
            # Confirm and analyze selected articles
            await _analyze_selected_articles(reaction, user, selection_data, selection_key)
            
        elif reaction.emoji == '🔥':
            # Select all articles
            selection_data['selected_indices'] = list(range(len(selection_data['articles'])))
            await _update_selection_display(reaction.message, selection_data)
            
        elif reaction.emoji in number_emojis:
            # Toggle article selection
            article_index = number_emojis.index(reaction.emoji)
            if article_index < len(selection_data['articles']):
                if article_index in selection_data['selected_indices']:
                    # Deselect
                    selection_data['selected_indices'].remove(article_index)
                else:
                    # Select
                    selection_data['selected_indices'].append(article_index)
                
                await _update_selection_display(reaction.message, selection_data)
        
        # Remove user's reaction to keep interface clean
        try:
            await reaction.remove(user)
        except:
            pass  # Ignore if bot can't remove reactions
            
    except Exception as e:
        logger.error(f"Error in reaction handler: {str(e)}")

async def _update_selection_display(message, selection_data):
    """Update the selection display to show currently selected articles."""
    selected_indices = selection_data['selected_indices']
    
    # Rebuild the embed with selection indicators
    title = f"🔍 Select Articles to Analyze"
    if selection_data['source']:
        title += f" - {selection_data['source']}"
    
    selected_count = len(selected_indices)
    description = f"**Select articles then click ✅ to analyze:**\n*Currently selected: {selected_count} articles*"
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=0xff4444
    )
    
    # Add articles with selection indicators
    article_list = ""
    display_articles = selection_data['articles']
    
    for i, article in enumerate(display_articles, 1):
        title_truncated = article['title'][:80] + "..." if len(article['title']) > 80 else article['title']
        published = ""
        if article.get('published_at'):
            try:
                pub_date = article['published_at']
                if isinstance(pub_date, str):
                    from datetime import datetime
                    pub_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                published = f" *({pub_date.strftime('%m/%d %H:%M')})*"
            except:
                published = ""
        
        # Add selection indicator
        selected_indicator = "✅ " if (i-1) in selected_indices else ""
        article_list += f"{selected_indicator}**{i}.** [{article['source']}] {title_truncated}{published}\n\n"
    
    embed.add_field(name="Available Articles", value=article_list, inline=False)
    
    footer_text = f"1️⃣-9️⃣ Select articles • 🔥 All articles • ✅ Confirm & analyze"
    if selected_count > 0:
        footer_text += f" • {selected_count} selected"
    embed.set_footer(text=footer_text)
    
    await message.edit(embed=embed)

async def _analyze_selected_articles(reaction, user, selection_data, selection_key):
    """Perform the analysis on selected articles."""
    selected_indices = selection_data['selected_indices']
    
    if not selected_indices:
        # No articles selected, show error
        embed = discord.Embed(
            title="❌ No Articles Selected",
            description="Please select at least one article before clicking ✅",
            color=0xff9900
        )
        await reaction.message.edit(embed=embed)
        return
    
    # Get selected articles
    selected_articles = [selection_data['articles'][i] for i in selected_indices]
    
    # Clear reactions and show analysis starting
    await reaction.message.clear_reactions()
    
    embed = discord.Embed(
        title="🔍 Analyzing Selected Articles...",
        description="Cutting through the BS and exposing the real story...",
        color=0xff4444
    )
    await reaction.message.edit(embed=embed)
    
    # Generate analysis title
    if len(selected_articles) == 1:
        analysis_title = f"🔍 Article Analysis - {selected_articles[0]['source']}"
    elif len(selected_indices) == len(selection_data['articles']):
        analysis_title = f"🔥 All Articles from {selection_data['source'] or 'Recent News'}"
    else:
        analysis_title = f"🔍 Selected Articles Analysis ({len(selected_articles)} articles)"
    
    # Get skeptical analysis
    if len(selected_articles) == 1:
        # Single article analysis
        article = selected_articles[0]
        ai_analysis = f"**Single Article Deep Dive:**\n\n"
        ai_analysis += f"**Title:** {article['title']}\n"
        ai_analysis += f"**Source:** {article['source']}\n"
        if article.get('published_at'):
            ai_analysis += f"**Published:** {article['published_at']}\n"
        ai_analysis += f"**URL:** {article['url']}\n\n"
        
        # Get detailed analysis of single article
        single_analysis = summarizer.analyze_news_collection_skeptical([article])
        ai_analysis += single_analysis
    else:
        # Multiple articles analysis
        ai_analysis = summarizer.analyze_news_collection_skeptical(selected_articles)
    
    # Create final embed with analysis
    embed = discord.Embed(
        title=analysis_title,
        description="**🔍 No-BS Analysis - Exposing the Real Story:**",
        color=0xff4444
    )
    
    # Handle long analysis (split if needed)
    max_embed_chars = 5500
    if len(ai_analysis) > max_embed_chars:
        ai_analysis = ai_analysis[:max_embed_chars] + "\n\n**[Analysis truncated due to length - select fewer articles for full analysis]**"
    
    if len(ai_analysis) > 1024:
        # Split into multiple fields
        analysis_parts = [ai_analysis[i:i+1024] for i in range(0, len(ai_analysis), 1024)]
        for i, part in enumerate(analysis_parts):
            field_title = "Analysis" if i == 0 else f"Analysis (continued {i+1})"
            embed.add_field(name=field_title, value=part, inline=False)
    else:
        embed.add_field(name="Analysis", value=ai_analysis, inline=False)
    
    # Add article links
    if len(selected_articles) > 1:
        article_links = "**Analyzed Articles:**\n"
        for i, article in enumerate(selected_articles[:5], 1):  # Limit to 5 for space
            article_links += f"{i}. [{article['source']}] {article['title'][:50]}...\n"
            article_links += f"   🔗 [Read More]({article['url']})\n"
        
        if len(article_links) < 1000:  # Only add if it fits
            embed.add_field(name="Source Articles", value=article_links, inline=False)
    
    embed.set_footer(text=f"Analysis requested by {user.display_name} | Articles: {len(selected_articles)}")
    
    await reaction.message.edit(embed=embed)
    
    # Clean up selection data
    del pending_selections[selection_key]

@bot.command(name='news')
async def fetch_news(ctx, *, source: str = None):
    """
    Interactive skeptical news analysis - select articles to analyze.
    Usage: |news [source]
    Example: |news CNN
    """
    try:
        limit = 10  # Get articles for selection
        
        # Send initial response
        embed = discord.Embed(
            title="🔍 Loading Articles...",
            description="Gathering articles for selection...",
            color=0xff4444
        )
        status_message = await ctx.send(embed=embed)
        
        # Get articles to display
        if source:
            # Try exact match first
            articles = database.get_articles_by_source(source, limit)
            
            # If no exact match, try partial match
            if not articles:
                all_articles = database.get_recent_articles(100)
                articles = [a for a in all_articles if source.lower() in a.get('source', '').lower()]
                articles = articles[:limit]
            
            if not articles:
                embed = discord.Embed(
                    title="📰 Source Not Found",
                    description=f"No articles found for source '{source}'. Use `|sources` to see available sources.",
                    color=0xff9900
                )
                await status_message.edit(embed=embed)
                return
        else:
            articles = database.get_recent_articles(limit)
        
        if not articles:
            embed = discord.Embed(
                title="📰 No Articles Found",
                description="No news articles are currently available. Use `|update` to fetch the latest news first.",
                color=0xff9900
            )
            await status_message.edit(embed=embed)
            return
        
        # Show article selection menu
        title = f"🔍 Select Articles to Analyze"
        if source:
            title += f" - {source}"
        
        embed = discord.Embed(
            title=title,
            description="**Select articles then click ✅ to analyze:**\n*React with 1️⃣-9️⃣ to select • 🔥 for all • ✅ to confirm*",
            color=0xff4444
        )
        
        # Add articles as options (limit to 9 for emoji reactions)
        article_list = ""
        display_articles = articles[:9]  # Max 9 for number emojis
        
        for i, article in enumerate(display_articles, 1):
            title_truncated = article['title'][:80] + "..." if len(article['title']) > 80 else article['title']
            published = ""
            if article.get('published_at'):
                try:
                    pub_date = article['published_at']
                    if isinstance(pub_date, str):
                        from datetime import datetime
                        pub_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    published = f" *({pub_date.strftime('%m/%d %H:%M')})*"
                except:
                    published = ""
            
            article_list += f"**{i}.** [{article['source']}] {title_truncated}{published}\n\n"
        
        embed.add_field(name="Available Articles", value=article_list, inline=False)
        embed.set_footer(text="1️⃣-9️⃣ Select articles • 🔥 All articles • ✅ Confirm & analyze")
        
        await status_message.edit(embed=embed)
        
        # Store selection state
        selection_key = f"{ctx.channel.id}_{status_message.id}_{ctx.author.id}"
        pending_selections[selection_key] = {
            'articles': display_articles,
            'source': source,
            'user_id': ctx.author.id,
            'channel_id': ctx.channel.id,
            'message_id': status_message.id,
            'timestamp': datetime.now(),
            'selected_indices': []  # Track selected article indices
        }
        
        # Add number reactions
        number_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
        for i in range(min(len(display_articles), 9)):
            await status_message.add_reaction(number_emojis[i])
        
        # Add "All" and "Confirm" options
        await status_message.add_reaction('🔥')  # All articles
        await status_message.add_reaction('✅')  # Confirm selection
        
    except Exception as e:
        logger.error(f"Error in news command: {str(e)}")
        embed = discord.Embed(
            title="❌ Error",
            description="Sorry, I encountered an error while loading articles. Please try again later.",
            color=0xff0000
        )
        await ctx.send(embed=embed)

@bot.command(name='update')
async def update_news(ctx):
    """
    Manually fetch and process latest news articles.
    This bypasses the 24-hour automatic fetch limit.
    """
    try:
        # Send initial response
        embed = discord.Embed(
            title="🔄 Fetching Latest News...",
            description="Please wait while I fetch and analyze the latest articles.",
            color=0x00ff00
        )
        status_message = await ctx.send(embed=embed)
        
        # Trigger manual news fetch
        article_count = await scheduler.manual_fetch()
        
        # Get fetch info
        fetch_info = scheduler.get_last_fetch_info()
        stats = database.get_database_stats()
        
        if article_count > 0:
            embed = discord.Embed(
                title="✅ News Update Complete",
                description=f"Successfully fetched and processed news articles.",
                color=0x00ff00
            )
            
            embed.add_field(
                name="📊 Update Results",
                value=f"• New articles processed: {article_count}\n• Total articles in database: {stats['total_articles']}\n• Sources: {stats['unique_sources']}",
                inline=False
            )
            
            embed.add_field(
                name="🕒 Timing",
                value=f"• Manual update: {fetch_info['last_manual_fetch'].strftime('%H:%M:%S %d/%m/%Y') if fetch_info['last_manual_fetch'] else 'Never'}\n• Last auto update: {fetch_info['last_auto_fetch'].strftime('%H:%M:%S %d/%m/%Y') if fetch_info['last_auto_fetch'] else 'Never'}",
                inline=False
            )
            
            embed.set_footer(text="Use |news to see AI analysis of the latest articles")
            
        else:
            embed = discord.Embed(
                title="📰 No New Articles",
                description="No new articles were found during this update.",
                color=0xff9900
            )
            
            embed.add_field(
                name="📊 Current Status",
                value=f"• Total articles in database: {stats['total_articles']}\n• Sources: {stats['unique_sources']}\n• Last update: {fetch_info['last_manual_fetch'].strftime('%H:%M %d/%m') if fetch_info['last_manual_fetch'] else 'Never'}",
                inline=False
            )
        
        await status_message.edit(embed=embed)
        
    except Exception as e:
        logger.error(f"Error in update command: {str(e)}")
        embed = discord.Embed(
            title="❌ Update Failed",
            description="Sorry, I encountered an error while updating news. Please try again later.",
            color=0xff0000
        )
        await ctx.send(embed=embed)

@bot.command(name='help')
async def show_help(ctx):
    """Show help information about the bot's capabilities."""
    help_text = responder._get_help_response()
    
    embed = discord.Embed(
        title="🧠 AI News Bot Help",
        description=help_text,
        color=0x0099ff
    )
    
    embed.set_footer(text="Use |command to run any command")
    await ctx.send(embed=embed)

@bot.command(name='sources')
async def list_sources(ctx):
    """List all available news sources in the database."""
    try:
        # Get all articles and extract unique sources
        recent_articles = database.get_recent_articles(limit=100)
        sources = {}
        
        for article in recent_articles:
            source = article.get('source', 'Unknown')
            if source not in sources:
                sources[source] = 0
            sources[source] += 1
        
        if not sources:
            embed = discord.Embed(
                title="📰 News Sources",
                description="No news sources available yet. Use `|update` to fetch articles first.",
                color=0xff9900
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="📰 Available News Sources",
            description="Here are the news sources currently in the database:",
            color=0x0099ff
        )
        
        source_list = ""
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
            source_list += f"• **{source}** ({count} articles)\n"
        
        embed.add_field(
            name="Sources",
            value=source_list,
            inline=False
        )
        
        embed.set_footer(text="Use '|news [source]' to get articles from a specific source (case insensitive)")
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error in sources command: {str(e)}")
        await ctx.send("Sorry, I encountered an error while fetching sources.")

@bot.command(name='analyze')
async def analyze_url(ctx, url: str = None):
    """
    Analyze an article from any URL for key points and people mentioned.
    Usage: |analyze [URL]
    Example: |analyze https://example.com/news-article
    """
    try:
        if not url:
            embed = discord.Embed(
                title="❌ URL Required",
                description="Please provide a URL to analyze.\nUsage: `|analyze [URL]`\nExample: `|analyze https://example.com/article`",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Send initial response
        embed = discord.Embed(
            title="🔍 Analyzing Article...",
            description=f"Extracting and analyzing content from:\n{url}",
            color=0xff4444
        )
        status_message = await ctx.send(embed=embed)
        
        # Extract article content using newspaper4k with fallback
        try:
            from newspaper import Article
            import requests
            from bs4 import BeautifulSoup
            
            article_title = "No title found"
            article_text = ""
            article_authors = ["Unknown"]
            article_publish_date = None
            
            # Try newspaper4k first
            try:
                article = Article(url)
                article.download()
                article.parse()
                
                if article.text:
                    article_title = article.title or "No title found"
                    article_text = article.text
                    article_authors = article.authors if article.authors else ["Unknown"]
                    article_publish_date = article.publish_date
                else:
                    raise Exception("No text extracted")
                    
            except Exception as newspaper_error:
                logger.warning(f"Newspaper4k failed: {str(newspaper_error)}, trying fallback method")
                
                # Fallback: Use requests + BeautifulSoup
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Try to extract title
                title_tag = soup.find('title') or soup.find('h1')
                if title_tag:
                    article_title = title_tag.get_text().strip()
                
                # Try to extract main content
                # Look for common article content containers
                content_selectors = [
                    'article', '[role="main"]', '.article-content', '.post-content',
                    '.entry-content', '.story-body', '.article-body', 'main'
                ]
                
                for selector in content_selectors:
                    content_div = soup.select_one(selector)
                    if content_div:
                        # Extract text from paragraphs
                        paragraphs = content_div.find_all('p')
                        if paragraphs:
                            article_text = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
                            if len(article_text) > 100:  # Only use if we got substantial content
                                break
                
                # If still no content, try all paragraphs on the page
                if not article_text or len(article_text) < 100:
                    paragraphs = soup.find_all('p')
                    article_text = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 50])
            
            if not article_text or len(article_text) < 50:
                embed = discord.Embed(
                    title="❌ Content Extraction Failed",
                    description="Could not extract readable content from the provided URL. The site may block automated access or require JavaScript.",
                    color=0xff0000
                )
                await status_message.edit(embed=embed)
                return
            
            # Prepare article data for analysis
            article_data = {
                'title': article_title,
                'url': url,
                'source': news_fetcher._extract_source_from_url(url),
                'published_at': article_publish_date,
                'summary': article_text[:200] + '...' if len(article_text) > 200 else article_text,
                'full_text': article_text,
                'authors': article_authors
            }
            
            # Get detailed analysis with key points and people mentioned
            analysis = summarizer.analyze_article_detailed(article_data)
            
            # Create analysis embed
            embed = discord.Embed(
                title="🔍 Article Analysis Complete",
                description=f"**Analysis of:** {article_data['title']}",
                color=0x00ff00
            )
            
            # Add basic info
            embed.add_field(
                name="📰 Article Info",
                value=f"**Source:** {article_data['source']}\n**Authors:** {', '.join(article_data['authors'])}\n**URL:** [Read Original]({url})",
                inline=False
            )
            
            # Add analysis content (split if too long)
            if len(analysis) > 1024:
                # Split into multiple fields
                analysis_parts = [analysis[i:i+1024] for i in range(0, len(analysis), 1024)]
                for i, part in enumerate(analysis_parts):
                    field_title = "🧠 Analysis" if i == 0 else f"🧠 Analysis (continued {i+1})"
                    embed.add_field(name=field_title, value=part, inline=False)
            else:
                embed.add_field(name="🧠 Analysis", value=analysis, inline=False)
            
            embed.set_footer(text=f"Analysis requested by {ctx.author.display_name}")
            
            await status_message.edit(embed=embed)
            
        except Exception as extraction_error:
            logger.error(f"Error extracting article content: {str(extraction_error)}")
            embed = discord.Embed(
                title="❌ Article Extraction Failed",
                description=f"Failed to extract content from the URL:\n```{str(extraction_error)}```\n\nThe website may:\n• Block automated access\n• Require JavaScript\n• Have restricted content\n• Be temporarily unavailable",
                color=0xff0000
            )
            await status_message.edit(embed=embed)
            
    except Exception as e:
        logger.error(f"Error in analyze command: {str(e)}")
        embed = discord.Embed(
            title="❌ Analysis Error",
            description="Sorry, I encountered an error while analyzing the article. Please check the URL and try again.",
            color=0xff0000
        )
        await ctx.send(embed=embed)

@bot.command(name='stats')
async def show_stats(ctx):
    """Display bot statistics."""
    try:
        stats = database.get_database_stats()
        
        embed = discord.Embed(
            title="📊 AI News Bot Statistics",
            color=0x9900ff
        )
        
        embed.add_field(
            name="📰 Total Articles",
            value=stats['total_articles'],
            inline=True
        )
        
        embed.add_field(
            name="🏢 Unique Sources",
            value=stats['unique_sources'],
            inline=True
        )
        
        embed.add_field(
            name="🕒 Last Update",
            value=stats['latest_update'] or "Never",
            inline=True
        )
        
        embed.add_field(
            name="🤖 Bot Status",
            value="Online and monitoring news",
            inline=True
        )
        
        embed.add_field(
            name="⏰ Auto-fetch Interval",
            value=f"Every {scheduler.fetch_interval_hours} hours",
            inline=True
        )
        
        embed.add_field(
            name="🔧 Commands",
            value="`|news` `|sources` `|stats` `|update` `|analyze` `|help`",
            inline=True
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error in stats command: {str(e)}")
        await ctx.send("Sorry, I encountered an error while fetching statistics.")

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors."""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    
    logger.error(f"Command error: {error}")
    await ctx.send("Sorry, something went wrong with that command. Please try again.")

async def shutdown_handler():
    """Handle graceful shutdown."""
    logger.info("Shutting down bot...")
    scheduler.stop_scheduler()
    await bot.close()

if __name__ == "__main__":
    # Check for required environment variables
    token = os.getenv('DISCORD_BOT_TOKEN')
    openai_key = os.getenv('OPENAI_API_KEY')
    
    if not token:
        logger.error("DISCORD_BOT_TOKEN not found in environment variables!")
        exit(1)
    
    if not openai_key:
        logger.error("OPENAI_API_KEY not found in environment variables!")
        exit(1)
    
    try:
        # Run the bot
        bot.run(token)
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    except Exception as e:
        logger.error(f"Bot error: {str(e)}")
    finally:
        # Cleanup
        if not bot.is_closed():
            asyncio.run(shutdown_handler())