# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI-powered Discord news bot built in Python that automatically fetches, analyzes, and summarizes news articles using OpenAI's GPT models. The bot provides skeptical, no-BS analysis of news from multiple international sources.

## Common Development Commands

### Running the Bot
```bash
python bot.py
```

### Installing Dependencies
```bash
pip install -r requirements.txt
```

### Environment Setup
```bash
cp .env.template .env
# Edit .env with required API keys and configuration
```

## Required Environment Variables

The bot requires these environment variables in `.env`:
- `DISCORD_BOT_TOKEN` - Discord bot token (required)
- `OPENAI_API_KEY` - OpenAI API key for GPT analysis (required)
- `NEWSAPI_KEY` - NewsAPI.org key (optional, fallback source)
- `RSS_FEEDS` - Comma-separated RSS feed URLs (optional, defaults to preset feeds)
- `DATABASE_NAME` - SQLite database filename (default: newsbot.db)
- `FETCH_INTERVAL_HOURS` - Automatic fetch interval (default: 24)

## Code Architecture

### Core Components

**bot.py** (Main Entry Point)
- Discord bot setup with `discord.py`
- Command handlers for `/news`, `/update`, `/sources`, `/stats`, `/help`
- Interactive article selection system using Discord reactions
- Mention handling for conversational responses
- Event handlers for bot lifecycle and error management

**database.py** (Data Layer)
- SQLite database management using `sqlite3`
- Article storage with schema: id, title, url, source, published_at, summary, intent, emotion, full_text, created_at
- Methods: `insert_article()`, `get_recent_articles()`, `search_articles()`, `get_articles_by_source()`, `get_database_stats()`
- **New methods for intelligent selection**: `get_all_article_titles()`, `get_articles_by_ids()` for AI-driven article selection
- **Enhanced response generation**: Strong citation requirements, current date awareness, and comprehensive article context integration

**news_fetcher.py** (News Acquisition)
- RSS feed parsing using `feedparser` with comprehensive error handling
- Full article content extraction using `newspaper4k`
- **Expanded source coverage**: 16 major news outlets including Fox News, NY Times, NBC, ABC, NPR, plus international sources
- Optional NewsAPI integration as fallback
- Enhanced source name mapping and URL extraction
- Detailed logging and feed success/failure tracking

**summarizer.py** (AI Analysis Engine)
- OpenAI GPT-4o-mini integration for cost-effective analysis
- Article summarization, intent detection, emotion analysis
- Skeptical news collection analysis focusing on bias detection
- Conversational AI responses for user interactions
- Unlimited batch processing without delays or rate limiting
- Automatic current date context injection for temporal awareness
- **Intelligent article selection**: Two-stage AI process that first selects relevant articles from entire database based on user questions, then generates comprehensive responses using selected articles
- **Per-source article selection**: AI selects up to 10 most important articles per news source based on breaking news, significance, international impact, and uniqueness
- **Enhanced response quality**: Explicit requirements for source citation, current date acknowledgment, and comprehensive article integration with URLs

**scheduler.py** (Background Processing)
- APScheduler for automated news fetching
- Manual and automatic fetch modes
- Duplicate article filtering
- Fetch timing management and statistics
- **US-emphasized source selection**: Prioritizes US sources (12 articles each) over international sources (5 articles each) for US-focused coverage
- **Controlled processing**: Bot may appear offline while analyzing selected articles, which is intentional and prevents user interaction during heavy processing

**responder.py** (Conversational AI)
- Handles Discord mentions and user questions
- Context-aware responses using recent conversation history
- News-related query detection and article search
- Integration with summarizer for intelligent responses
- **Intelligent article selection flow**: Uses AI to select most relevant articles from entire database before generating responses, with fallback to keyword-based search

### Key Design Patterns

**Interactive Article Selection**: Bot presents articles with numbered reactions (1️⃣-9️⃣), users select multiple articles, then confirm with ✅ for batch analysis.

**Skeptical Analysis Approach**: AI system prompts emphasize critical thinking, bias detection, and "cui bono" (who benefits) analysis rather than standard news summarization.

**Multi-Source Integration**: Supports both RSS feeds and NewsAPI with graceful fallbacks and robust error handling for international sources.

**Context Management**: Stores pending selections in memory with automatic cleanup, maintains conversation context for natural interactions.

**Intelligent Article Selection (Two-Stage AI Process)**:
1. **Stage 1 - Selection**: When user asks a question, AI receives the question + titles of all articles in database (up to 100 recent articles), then selects up to 10 most relevant article IDs
   - **US Source Prioritization**: For US political questions (containing keywords like "us politics", "congress", "biden", "trump", etc.), the AI strongly prioritizes US sources (CNN, Fox News, Reuters, NY Times, Washington Post, NBC, ABC, NPR) over international sources
   - **Source Marking**: Articles are marked as [US SOURCE] or [INTL SOURCE] to guide AI selection
   - **Geographic Relevance**: US political questions aim for 70% US sources, while international questions consider source diversity
2. **Stage 2 - Response**: AI receives the user's question + full content of selected articles, then generates comprehensive response synthesizing information from multiple sources
3. **Fallback System**: If intelligent selection fails, falls back to keyword-based search for reliability

**US-Emphasized Source Coverage**:
1. **Source Classification**: All sources are categorized as US or International
   - **US Sources**: CNN, Fox News, NY Times, Washington Post, NBC News, ABC News, NPR, Reuters
   - **International Sources**: BBC, Al Jazeera, RT News, Tehran Times, Jerusalem Post, etc.
2. **Prioritized Selection**: 
   - **US Sources**: Up to 12 most recent articles each (higher priority)
   - **International Sources**: Up to 5 most recent articles each (global perspective)
3. **US-Focused Coverage**: Ensures comprehensive US news coverage while maintaining international context
4. **Reliable & Simple**: Fast, predictable selection without AI complexity

## Discord Commands

- `|news` - Interactive article selection and analysis
- `|news [source]` - Filter articles by specific news source
- `|update` - Manual news fetch bypassing automatic schedule
- `|sources` - List all available news sources with article counts
- `|stats` - Display bot and database statistics
- `|help` - Show help information

## Database Schema

```sql
CREATE TABLE articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    source TEXT,
    published_at DATETIME,
    summary TEXT,
    intent TEXT,
    emotion TEXT,
    full_text TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Development Notes

- **No Package.json**: This is a pure Python project using pip/requirements.txt
- **No Test Framework**: No automated tests are configured
- **Bot Prefix**: Uses `|` as command prefix (not `/` slash commands)
- **AI Model**: Uses GPT-4o-mini for cost efficiency
- **No Rate Limiting**: All delays between OpenAI API calls removed for maximum processing speed
- **Message Limits**: Discord embeds truncated at 2000/5500 characters
- **US-Emphasized Coverage**: Bot prioritizes US sources (up to 12 articles each) while maintaining international perspective (up to 5 articles each)
- **Comprehensive Source Coverage**: Now includes Fox News, New York Times, NBC News, ABC News, NPR, plus international sources (RT, Al Jazeera, Tehran Times, BBC, etc.)

## Error Handling Philosophy

The bot is designed to be resilient with extensive try-catch blocks, graceful fallbacks when article parsing fails, and continued operation even when individual news sources are unavailable. All errors are logged but don't crash the bot.