import os
import logging
import asyncio
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import tempfile
import shutil

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Your bot token from BotFather
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

class MusicBot:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /start is issued."""
        welcome_message = (
            "🎵 Welcome to Music Bot! 🎵\n\n"
            "Send me a song request using:\n"
            "/song <song name or artist - song title>\n\n"
            "Example:\n"
            "/song Imagine Dragons - Believer\n"
            "/song Shape of You Ed Sheeran\n\n"
            "I'll search and download the song for you!\n"
            "OG owner :- @mahadev_ki_iccha "
        )
        await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /help is issued."""
        help_text = (
            "🎵 Music Bot Commands:\n\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/song <song name> - Download and send a song\n\n"
            "Just type the song name after /song and I'll find it for you!"
        )
        await update.message.reply_text(help_text)

    def get_ydl_opts(self, output_path):
        """Configure yt-dlp options for audio download."""
        return {
            'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio',
            'outtmpl': output_path,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',  # Lower quality for faster processing
            }],
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'writeinfojson': False,
            'writethumbnail': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'ignoreerrors': True,
            'no_color': True,
            'concurrent_fragment_downloads': 4,  # Faster downloads
        }

    async def download_song(self, query):
        """Download song from YouTube based on search query."""
        try:
            # Create a unique filename
            filename = f"song_{hash(query) % 10000}"
            output_path = os.path.join(self.temp_dir, f"{filename}.%(ext)s")
            
            # Configure yt-dlp with optimized settings
            ydl_opts = self.get_ydl_opts(output_path)
            
            # Use more specific search to get better results faster
            search_query = f"ytsearch1:{query} audio"
            
            def download_in_thread():
                """Run download in a separate thread to avoid blocking."""
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    try:
                        # Extract info first
                        info = ydl.extract_info(search_query, download=False)
                        if not info or 'entries' not in info or not info['entries']:
                            return None, None, "No results found"
                        
                        video_info = info['entries'][0]
                        title = video_info.get('title', 'Unknown')
                        duration = video_info.get('duration', 0)
                        
                        # Check duration (limit to 8 minutes for faster processing)
                        if duration and duration > 480:
                            return None, None, "Song is too long (max 8 minutes allowed)"
                        
                        # Download the audio
                        ydl.download([search_query])
                        return video_info, title, None
                        
                    except Exception as e:
                        return None, None, str(e)
            
            # Run download in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            video_info, title, error = await loop.run_in_executor(None, download_in_thread)
            
            if error:
                return None, error
            
            # Find the downloaded file
            mp3_file = f"{os.path.join(self.temp_dir, filename)}.mp3"
            if os.path.exists(mp3_file):
                return mp3_file, title
            else:
                # Try to find any mp3 file with the filename prefix
                for file in os.listdir(self.temp_dir):
                    if file.startswith(filename) and file.endswith('.mp3'):
                        return os.path.join(self.temp_dir, file), title
                
                return None, "Download completed but file not found"
                    
        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            return None, f"Error: {str(e)}"

    async def song_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /song command."""
        if not context.args:
            await update.message.reply_text(
                "Please provide a song name!\n"
                "Example: /song Imagine Dragons - Believer"
            )
            return

        query = " ".join(context.args)
        
        # Send initial message
        status_message = await update.message.reply_text(
            f"🔍 Searching for: {query}\n⏳ Downloading... Please wait"
        )
        
        try:
            # Download the song without timeout
            file_path, result = await self.download_song(query)
            
            if file_path and os.path.exists(file_path):
                # Update status
                await status_message.edit_text("⬆️ Uploading song...")
                
                # Check file size (Telegram limit is 50MB)
                file_size = os.path.getsize(file_path)
                if file_size > 50 * 1024 * 1024:  # 50MB
                    await status_message.edit_text("❌ File too large (max 50MB)")
                    os.remove(file_path)
                    return
                
                # Send the audio file
                with open(file_path, 'rb') as audio:
                    await update.message.reply_audio(
                        audio=audio,
                        title=result,
                        performer="AyushXmusic",
                        caption=f"🎵 {result}",
                        read_timeout=120,
                        write_timeout=120
                    )
                
                # Delete status message and cleanup
                await status_message.delete()
                os.remove(file_path)
                
            else:
                await status_message.edit_text(f"❌ {result}")
                
        except Exception as e:
            logger.error(f"Song command error: {str(e)}")
            await status_message.edit_text(f"❌ An error occurred: {str(e)}")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Log errors caused by Updates."""
        logger.warning(f'Update {update} caused error {context.error}')

    def cleanup(self):
        """Clean up temporary directory."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

def main():
    """Start the bot."""
    # Create bot instance
    music_bot = MusicBot()
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", music_bot.start))
    application.add_handler(CommandHandler("help", music_bot.help_command))
    application.add_handler(CommandHandler("song", music_bot.song_command))
    
    # Add error handler
    application.add_error_handler(music_bot.error_handler)

    # Run the bot
    try:
        print("🎵 Music Bot is starting...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("🛑 Bot stopped by user")
    finally:
        music_bot.cleanup()

if __name__ == '__main__':
    main()
