from telegram import ReplyKeyboardMarkup, KeyboardButton
from openai import OpenAI

class StickerHandler:
    def __init__(self, openai_client, mood_manager, db_manager, channel_username):
        self.client = openai_client
        self.mood_manager = mood_manager
        self.db = db_manager
        self.channel_username = channel_username
        self.GPT_MAX_TOKENS = 600
        self.GPT_TEMPERATURE = 1.1
        self.GPT_MODEL = "gpt-4o-mini"

    async def handle_sticker(self, update, context):
        if update.channel_post:
            return

        try:
            user_id = update.effective_user.id
            sticker = update.message.sticker
            
            is_subscribed = await self.check_subscription(user_id, context.bot)
            if not is_subscribed:
                keyboard = [[KeyboardButton(f"Подписаться на {self.channel_username}")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(
                    f"Хей~ Чтобы отправлять мне стикеры, подпишись на канал {self.channel_username} 💙",
                    reply_markup=reply_markup
                )
                return

            sticker_description = f"[Стикер: {sticker.emoji if sticker.emoji else 'без эмодзи'}]"
            self.db.store_message(user_id, sticker_description, 'user')
            
            if sticker.emoji:
                sentiment_score = self.mood_manager.analyze_sentiment(sticker.emoji)
                self.mood_manager.update_mood(user_id, sentiment_score)

            messages = self.get_conversation_messages(user_id)
            
            try:
                response = self.client.chat.completions.create(
                    model=self.GPT_MODEL,
                    messages=messages,
                    max_tokens=self.GPT_MAX_TOKENS,
                    temperature=self.GPT_TEMPERATURE
                )
                bot_response = response.choices[0].message.content
                self.db.store_message(user_id, bot_response, 'assistant')
                
                keyboard = [[KeyboardButton("Очистить память")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(bot_response, reply_markup=reply_markup)
                
            except Exception as e:
                print(f"Error in GPT response for sticker: {e}")
                await update.message.reply_text("Извини, что-то пошло не так при обработке стикера...")
                
        except Exception as e:
            print(f"Error in sticker handling: {e}")
            if update.message:
                await update.message.reply_text("Произошла ошибка при обработке стикера...")

    async def check_subscription(self, user_id, bot):
        try:
            member = await bot.get_chat_member(chat_id=self.channel_username, user_id=user_id)
            return member.status in ['member', 'administrator', 'creator']
        except Exception as e:
            print(f"Error checking subscription: {e}")
            return False

    def get_conversation_messages(self, user_id):
        history = self.db.get_conversation_history(user_id)
        system_prompt = self.mood_manager.get_system_prompt(user_id)
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        for msg, role in history:
            messages.append({"role": role, "content": msg})
        
        return messages
