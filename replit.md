# Telegram Channel Management Bot

A comprehensive Telegram bot for channel management, view boosting, and live stream automation using Python, aiogram, and Telethon.

## 🔥 CRITICAL DATABASE RULES - READ FIRST! 🔥

**MANDATORY RULE BOOK FOR ALL AGENTS:**

1. **🚨 NEVER USE REPLIT DATABASE** - This project MUST use external telethon_db only
2. **✅ ALWAYS USE TELETHON_DB** - Located at 18.234.56.13, database name: telethon_db
3. **⚠️ DELETE ANY REPLIT DATABASE** - If created accidentally, delete it immediately
4. **📋 DATABASE CONFIG SOURCE** - All database settings come from `data.env` file ONLY
5. **🔒 NO EXCEPTIONS** - External telethon_db is the ONLY allowed database

### Database Configuration:
- **Host:** 18.234.56.13 (from data.env)
- **Database:** telethon_db (from data.env) 
- **User:** arcx (from data.env)
- **Port:** 5432 (from data.env)
- **Password:** From data.env file

### What to do if Replit database exists:
1. Delete it immediately
2. Restart the bot workflow
3. Verify logs show connection to 18.234.56.13/telethon_db
4. Never create or provision Replit databases

## 🚀 Features

### Core Features
- **Channel Management** - Add, configure, and manage multiple Telegram channels
- **View Boosting** - Automatic and manual view boosting with scheduling
- **Live Stream Management** - Auto-join live streams and voice chats
- **Multi-Account Support** - Manage up to 100 Telegram accounts simultaneously
- **Emoji Reactions** - Automated emoji reactions on posts
- **Real-time Analytics** - Comprehensive performance monitoring
- **System Health** - Bot performance and resource monitoring

### Technical Features
- **External PostgreSQL** - Mandatory external database integration
- **Rate Limiting** - Telegram API compliance with intelligent throttling
- **Session Management** - Secure handling of multiple account sessions
- **Modular Architecture** - Clean separation of features and concerns
- **Error Handling** - Comprehensive error recovery and logging
- **Resource Management** - Automatic cleanup and optimization

## 🏗️ Architecture

### File Structure
