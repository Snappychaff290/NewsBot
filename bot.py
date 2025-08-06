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
    """Handle reaction-based article selection."""
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
        selected_articles = []
        
        if reaction.emoji == '🔥':
            # Analyze all articles
            selected_articles = selection_data['articles']
            analysis_title = f"🔥 All Articles from {selection_data['source'] or 'Recent News'}"
        elif reaction.emoji in number_emojis:
            # Analyze specific article
            article_index = number_emojis.index(reaction.emoji)
            if article_index < len(selection_data['articles']):
                selected_articles = [selection_data['articles'][article_index]]
                analysis_title = f"🔍 Article Analysis - {selected_articles[0]['source']}"
        else:
            return  # Unknown reaction
        
        if not selected_articles:
            return
        
        # Clear reactions and update message to show analysis is starting
        await reaction.message.clear_reactions()
        
        embed = discord.Embed(
            title="🔍 Analyzing Selected Articles...",
            description="Cutting through the BS and exposing the real story...",
            color=0xff4444
        )
        await reaction.message.edit(embed=embed)
        
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
        
    except Exception as e:
        logger.error(f"Error in reaction handler: {str(e)}")
        embed = discord.Embed(
            title="❌ Analysis Error",
            description="Sorry, I encountered an error while analyzing the selected articles.",
            color=0xff0000
        )
        await reaction.message.edit(embed=embed)
        
        # Clean up selection data
        if selection_key in pending_selections:
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
            description="**React with number emojis to select articles for skeptical analysis:**\n*Multiple selections allowed*",
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
        embed.set_footer(text="React with 1️⃣-9️⃣ to select articles • Multiple selections allowed")
        
        await status_message.edit(embed=embed)
        
        # Store selection state
        selection_key = f"{ctx.channel.id}_{status_message.id}_{ctx.author.id}"
        pending_selections[selection_key] = {
            'articles': display_articles,
            'source': source,
            'user_id': ctx.author.id,
            'channel_id': ctx.channel.id,
            'message_id': status_message.id,
            'timestamp': datetime.now()
        }
        
        # Add number reactions
        number_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
        for i in range(min(len(display_articles), 9)):
            await status_message.add_reaction(number_emojis[i])
        
        # Add "All" option
        await status_message.add_reaction('🔥')  # All articles
        
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
            value="`|news` `|sources` `|stats` `|update` `|help`",
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