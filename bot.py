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
            name="📰 the latest news"
        )
    )
    
    print(f"🧠 AI News Bot is online!")
    print(f"📊 Database: {database.get_database_stats()['total_articles']} articles stored")

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

@bot.command(name='news')
async def fetch_news(ctx, *, source: str = None):
    """
    Analyze and display latest news with AI summary.
    Usage: |news [source]
    Example: |news CNN
    """
    try:
        limit = 10  # Fixed limit for better analysis
        
        # Send initial response
        embed = discord.Embed(
            title="🧠 Analyzing Latest News...",
            description="Please wait while I analyze the latest articles with AI.",
            color=0x00ff00
        )
        status_message = await ctx.send(embed=embed)
        
        # Get articles to display (don't fetch new ones, use existing)
        if source:
            # Try exact match first
            articles = database.get_articles_by_source(source, limit)
            
            # If no exact match, try partial match
            if not articles:
                all_articles = database.get_recent_articles(100)  # Get more for searching
                articles = [a for a in all_articles if source.lower() in a.get('source', '').lower()]
                articles = articles[:limit]
            
            if not articles:
                # Show available sources if no match found
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
        
        # Get AI analysis of the articles
        ai_analysis = summarizer.analyze_news_collection(articles)
        
        # Create response embed with AI analysis
        title = f"🧠 AI News Analysis"
        if source:
            title += f" - {source}"
        
        embed = discord.Embed(
            title=title,
            description="**AI Analysis of Recent News:**",
            color=0x9900ff
        )
        
        # Add AI analysis as main content
        if len(ai_analysis) > 1024:
            # Split long analysis into multiple fields
            analysis_parts = [ai_analysis[i:i+1024] for i in range(0, len(ai_analysis), 1024)]
            for i, part in enumerate(analysis_parts):
                field_title = "Analysis" if i == 0 else f"Analysis (continued {i+1})"
                embed.add_field(name=field_title, value=part, inline=False)
        else:
            embed.add_field(name="Analysis", value=ai_analysis, inline=False)
        
        # Add top articles summary
        article_summary = f"**Top {min(5, len(articles))} Articles:**\n"
        for i, article in enumerate(articles[:5], 1):
            article_summary += f"{i}. **{article['source']}** - {article['title'][:80]}...\n"
            article_summary += f"   🔗 [Read More]({article['url']})\n"
        
        embed.add_field(name="Featured Articles", value=article_summary, inline=False)
        
        # Add database stats
        stats = database.get_database_stats()
        fetch_info = scheduler.get_last_fetch_info()
        footer_text = f"Articles analyzed: {len(articles)} | Total in DB: {stats['total_articles']}"
        if fetch_info['last_auto_fetch']:
            footer_text += f" | Last update: {fetch_info['last_auto_fetch'].strftime('%H:%M %d/%m')}"
        
        embed.set_footer(text=footer_text)
        
        await status_message.edit(embed=embed)
        
    except Exception as e:
        logger.error(f"Error in news command: {str(e)}")
        embed = discord.Embed(
            title="❌ Error",
            description="Sorry, I encountered an error while analyzing news. Please try again later.",
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