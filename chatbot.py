import os
import sqlite3
from datetime import datetime
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from openai import OpenAI
import sys
import base64
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from mood_manager import MoodManager
from image_handler import ImageHandler
from voice_handler import VoiceHandler
from sticker_handler import StickerHandler

# Конфигурационные константы
TELEGRAM_BOT_TOKEN = 'ваш апи'
FORGET_API_KEY = 'ваш апи'
ASSEMBLYAI_API_KEY = 'ваш апи'
CHANNEL_USERNAME = 'ваш тг канал, сделайте бота админом в нём'

# Константы для GPT
GPT_TEMPERATURE = 1.1
GPT_MAX_TOKENS = 600
GPT_MODEL = "gpt-4o-mini"

client = OpenAI(
    api_key=FORGET_API_KEY,
    base_url="https://forgetapi.ru/v1"
)

class TimeManager:
    def __init__(self, db_manager):
        self.db = db_manager
        self.user_activities = {}

    def get_current_time(self):
        return datetime.now()

    def store_user_activity(self, user_id, activity_type, details=None):
        current_time = self.get_current_time()
        if user_id not in self.user_activities:
            self.user_activities[user_id] = []
        
        self.user_activities[user_id].append({
            'type': activity_type,
            'time': current_time,
            'details': details
        })

    def get_time_since_last_interaction(self, user_id, activity_type=None):
        if user_id not in self.user_activities:
            return None

        current_time = self.get_current_time()
        activities = self.user_activities[user_id]
        
        if activity_type:
            activities = [a for a in activities if a['type'] == activity_type]
        
        if not activities:
            return None
            
        last_activity = max(activities, key=lambda x: x['time'])
        time_diff = current_time - last_activity['time']
        return time_diff

    def extract_time_mentions(self, message):
        time_indicators = ['пойду', 'схожу', 'иду', 'пойдём', 'собираюсь']
        locations = ['магазин', 'аптека', 'школа', 'работа']
        
        message_lower = message.lower()
        
        for indicator in time_indicators:
            if indicator in message_lower:
                for location in locations:
                    if location in message_lower:
                        return {
                            'action': indicator,
                            'location': location,
                            'mentioned_time': self.get_current_time()
                        }
        return None

    def format_time_difference(self, time_diff):
        if not time_diff:
            return None
            
        minutes = time_diff.total_seconds() / 60
        hours = minutes / 60
        
        if minutes < 1:
            return "меньше минуты назад"
        elif minutes < 60:
            return f"{int(minutes)} минут назад"
        elif hours < 24:
            return f"{int(hours)} часов назад"
        else:
            days = int(hours / 24)
            return f"{days} дней назад"

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect('chatbot.db', check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            user_id INTEGER,
            message TEXT,
            timestamp DATETIME,
            role TEXT
        )''')
        self.conn.commit()

    def store_message(self, user_id, message, role='user'):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO conversations (user_id, message, timestamp, role)
        VALUES (?, ?, ?, ?)
        ''', (user_id, message, datetime.now(), role))
        self.conn.commit()

    def get_conversation_history(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT message, role FROM conversations 
        WHERE user_id = ? 
        ORDER BY timestamp ASC
        ''', (user_id,))
        return cursor.fetchall()

    def clear_history(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM conversations WHERE user_id = ?', (user_id,))
        self.conn.commit()

    def close(self):
        self.conn.close()

class ChatBot:
    def __init__(self):
        self.db = DatabaseManager()
        self.mood_manager = MoodManager()
        self.voice_handler = VoiceHandler(ASSEMBLYAI_API_KEY)
        self.image_handler = ImageHandler(client, self.mood_manager, self.db, CHANNEL_USERNAME)
        self.sticker_handler = StickerHandler(client, self.mood_manager, self.db, CHANNEL_USERNAME)
        self.time_manager = TimeManager(self.db)

    async def check_subscription(self, user_id, bot):
        try:
            member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
            return member.status in ['member', 'administrator', 'creator']
        except Exception as e:
            print(f"Error checking subscription: {e}")
            return False

    def get_conversation_messages(self, user_id):
        history = self.db.get_conversation_history(user_id)
        system_prompt = self.mood_manager.get_system_prompt(user_id)
        
        last_user_time = self.time_manager.get_time_since_last_interaction(user_id, 'user_message')
        last_bot_time = self.time_manager.get_time_since_last_interaction(user_id, 'bot_message')
        
        time_context = f"""
        Текущее время: {self.time_manager.get_current_time().strftime('%H:%M %d.%m.%Y')}
        Последнее сообщение пользователя: {self.time_manager.format_time_difference(last_user_time)}
        Мой последний ответ: {self.time_manager.format_time_difference(last_bot_time)}
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": time_context}
        ]
        
        for msg, role in history:
            messages.append({"role": role, "content": msg})
        
        return messages

    async def handle_message(self, update, context):
        if update.channel_post:
            return

        try:
            user_id = update.effective_user.id
            user_message = update.message.text

            if not user_message:
                return

            self.time_manager.store_user_activity(user_id, 'user_message')
            
            time_mention = self.time_manager.extract_time_mentions(user_message)
            if time_mention:
                self.time_manager.store_user_activity(user_id, 'plan', time_mention)

            is_subscribed = await self.check_subscription(user_id, context.bot)
            if not is_subscribed:
                keyboard = [[KeyboardButton(f"Подписаться на {CHANNEL_USERNAME}")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(
                    f"Хей~ Чтобы общаться со мной, подпишись на канал {CHANNEL_USERNAME} 💙\n"
                    f"После подписки отправь сообщение еще раз!",
                    reply_markup=reply_markup
                )
                return

            if user_message.lower() == "очистить память":
                return await self.clear_memory(update, context)

            sentiment_score = self.mood_manager.analyze_sentiment(user_message)
            self.mood_manager.update_mood(user_id, sentiment_score)

            self.db.store_message(user_id, user_message, 'user')
            messages = self.get_conversation_messages(user_id)

            try:
                response = client.chat.completions.create(
                    model=GPT_MODEL,
                    messages=messages,
                    max_tokens=GPT_MAX_TOKENS,
                    temperature=GPT_TEMPERATURE
                )
                bot_response = response.choices[0].message.content
                
                self.time_manager.store_user_activity(user_id, 'bot_message')
                self.db.store_message(user_id, bot_response, 'assistant')
                
                last_plan = None
                if user_id in self.time_manager.user_activities:
                    plans = [a for a in self.time_manager.user_activities[user_id] if a['type'] == 'plan']
                    if plans:
                        last_plan = plans[-1]

                time_context = ""
                if last_plan:
                    time_since_plan = datetime.now() - last_plan['details']['mentioned_time']
                    if time_since_plan.total_seconds() < 7200:
                        location = last_plan['details']['location']
                        time_context = f"\n\nКстати, ты недавно упоминал(а) о походе в {location}. Как всё прошло?"

                keyboard = [[KeyboardButton("Очистить память")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(bot_response + time_context, reply_markup=reply_markup)
                
            except Exception as e:
                print(f"Error in GPT response: {e}")
                await update.message.reply_text("Извини, что-то пошло не так. Давай попробуем еще раз?")
                
        except Exception as e:
            print(f"Error in message handling: {e}")
            if update.message:
                await update.message.reply_text("Произошла ошибка при обработке сообщения...")

    async def handle_sticker(self, update, context):
        await self.sticker_handler.handle_sticker(update, context)

    async def handle_channel_post(self, update, context):
        if update.channel_post and update.channel_post.chat.username == CHANNEL_USERNAME.replace('@', ''):
            print(f"Новый пост в канале: {update.channel_post.text}")
            return

    async def handle_photo(self, update, context):
        if update.channel_post:
            return
        await self.image_handler.handle_photo(update, context)

    async def start(self, update, context):
        if update.channel_post:
            return

        try:
            user_id = update.effective_user.id
            
            is_subscribed = await self.check_subscription(user_id, context.bot)
            if not is_subscribed:
                keyboard = [[KeyboardButton(f"Подписаться на {CHANNEL_USERNAME}")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(
                    f"Привет! Я Ария~ Чтобы начать общение, подпишись на канал {CHANNEL_USERNAME} 💙\n"
                    f"После подписки нажми /start еще раз!",
                    reply_markup=reply_markup
                )
                return
            
            keyboard = [[KeyboardButton("Очистить память")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            welcome_message = 'Привет! Я Ария, рада познакомиться! 💙\n\nЯ эмоциональный бот, и моё настроение зависит от того, как со мной общаются. Давай поболтаем!'
            
            self.db.store_message(user_id, welcome_message, 'assistant')
            
            await update.message.reply_text(
                welcome_message,
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Error in start command: {e}")
            if update.message:
                await update.message.reply_text("Извини, что-то пошло не так при запуске...")

    async def clear_memory(self, update, context):
        if update.channel_post:
            return

        try:
            user_id = update.effective_user.id
            
            is_subscribed = await self.check_subscription(user_id, context.bot)
            if not is_subscribed:
                keyboard = [[KeyboardButton(f"Подписаться на {CHANNEL_USERNAME}")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(
                    f"Хей~ Чтобы использовать мои функции, подпишись на канал {CHANNEL_USERNAME} 💙",
                    reply_markup=reply_markup
                )
                return
            
            self.db.clear_history(user_id)
            self.mood_manager.set_initial_mood(user_id)
            await update.message.reply_text("Я начала новую страницу в нашем общении! 💙")
        except Exception as e:
            print(f"Error in clearing memory: {e}")
            if update.message:
                await update.message.reply_text("Произошла ошибка при очистке памяти...")

    async def handle_voice(self, update, context):
        if update.channel_post:
            return

        try:
            user_id = update.effective_user.id
            
            is_subscribed = await self.check_subscription(user_id, context.bot)
            if not is_subscribed:
                keyboard = [[KeyboardButton(f"Подписаться на {CHANNEL_USERNAME}")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(
                    f"Хей~ Чтобы отправлять мне голосовые сообщения, подпишись на канал {CHANNEL_USERNAME} 💙",
                    reply_markup=reply_markup
                )
                return
            
            voice = update.message.voice
            
            try:
                file = await context.bot.get_file(voice.file_id)
                voice_file = await file.download_as_bytearray()
                
                transcript = self.voice_handler.transcribe_audio(voice_file)
                
                if transcript:
                    await update.message.reply_text(f"Я услышала: {transcript}")
                    
                    sentiment_score = self.mood_manager.analyze_sentiment(transcript)
                    self.mood_manager.update_mood(user_id, sentiment_score)
                    
                    self.db.store_message(user_id, transcript, 'user')
                    messages = self.get_conversation_messages(user_id)
                    
                    try:
                        response = client.chat.completions.create(
                            model=GPT_MODEL,
                            messages=messages,
                            max_tokens=GPT_MAX_TOKENS,
                            temperature=GPT_TEMPERATURE
                        )
                        bot_response = response.choices[0].message.content
                        self.db.store_message(user_id, bot_response, 'assistant')
                        
                        keyboard = [[KeyboardButton("Очистить память")]]
                        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                        await update.message.reply_text(bot_response, reply_markup=reply_markup)
                    except Exception as e:
                        print(f"Error in GPT response for voice: {e}")
                        await update.message.reply_text("Извини, не смогла сформулировать ответ на голосовое сообщение...")
                else:
                    await update.message.reply_text("Извини, не смогла разобрать аудиосообщение... Можешь повторить?")
                    
            except Exception as e:
                print(f"Error in voice processing: {e}")
                await update.message.reply_text("Произошла ошибка при обработке голосового сообщения...")
                
        except Exception as e:
            print(f"Error in voice handling: {e}")
            if update.message:
                await update.message.reply_text("Произошла ошибка при обработке голосового сообщения...")

    async def error_handler(self, update, context):
        """Улучшенный обработчик ошибок"""
        print(f'Update {update} caused error {context.error}')
        
        if update and update.effective_message and not update.channel_post:
            await update.effective_message.reply_text(
                "Произошла непредвиденная ошибка. Попробуйте позже или начните новый диалог командой /start"
            )

    def __del__(self):
        try:
            self.db.close()
        except:
            pass

def main():
    try:
        print("Starting bot...")
        bot = ChatBot()
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Стандартные обработчики с исправленными фильтрами
        application.add_handler(CommandHandler("start", bot.start))
        
        # Фильтр для текстовых сообщений
        text_filter = (
            filters.TEXT & 
            ~filters.COMMAND & 
            filters.ChatType.PRIVATE
        )
        application.add_handler(MessageHandler(text_filter, bot.handle_message))
        
        # Фильтр для голосовых сообщений
        voice_filter = filters.VOICE & filters.ChatType.PRIVATE
        application.add_handler(MessageHandler(voice_filter, bot.handle_voice))
        
        # Фильтр для фотографий
        photo_filter = filters.PHOTO & filters.ChatType.PRIVATE
        application.add_handler(MessageHandler(photo_filter, bot.handle_photo))
        
        # Фильтр для стикеров
        sticker_filter = filters.Sticker.ALL & filters.ChatType.PRIVATE
        application.add_handler(MessageHandler(sticker_filter, bot.handle_sticker))
        
        # Фильтр для постов в канале
        channel_filter = filters.ChatType.CHANNEL
        application.add_handler(MessageHandler(channel_filter, bot.handle_channel_post))
        
        # Обработчик ошибок
        application.add_error_handler(bot.error_handler)

        print("Bot is running...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"Critical error in main: {e}")

if __name__ == '__main__':
    main()