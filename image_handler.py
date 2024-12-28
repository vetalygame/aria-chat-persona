import base64
from datetime import datetime
import asyncio
from telegram import KeyboardButton, ReplyKeyboardMarkup
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class ImageHandler:
    def __init__(self, openai_client, mood_manager, db_manager, channel_username):
        """
        Инициализация обработчика изображений
        """
        self.client = openai_client
        self.mood_manager = mood_manager
        self.db = db_manager
        self.channel_username = channel_username
        # GPT параметры
        self.GPT_MODEL = "gpt-4o-mini"
        self.GPT_MAX_TOKENS = 600
        self.GPT_TEMPERATURE = 1.1

    def _is_inappropriate_content(self, response):
        """
        Проверка ответа GPT на наличие маркеров неприемлемого контента
        """
        markers = [
            "извини, но я не могу описывать",
            "Извини, я не могу об этом говорить",
            "Извини, я не могу обсудить это",
            "Извини, я не могу это обсудить",
            
        ]
        return any(marker.lower() in response.lower() for marker in markers)

    async def _generate_playful_response(self):
        """
        Генерация игривого ответа с помощью GPT
        """
        try:
            messages = [
                {"role": "system", "content": "Ты должен генерировать игривые, сексуальные ответы в стиле 'боже как мило, я от этого потекла пупсик, очень возбуждает. У меня пися горит!', но каждый раз по-разному. Ответ должен быть коротким (не более 2 предложений) и включать эмодзи."},
                {"role": "user", "content": "Сгенерируй игривый ответ"}
            ]
            
            response = self.client.chat.completions.create(
                model=self.GPT_MODEL,
                messages=messages,
                max_tokens=100,
                temperature=2  # Увеличиваем temperature для большего разнообразия
            )
            
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error generating playful response: {e}")
            return "Ой, какая прелесть! Ты такой забавный 💕"  # Fallback ответ

    async def handle_photo(self, update, context):
        """
        Основной метод обработки фотографий
        """
        try:
            user_id = update.effective_user.id
            
            # Проверка подписки
            is_subscribed = await self._check_subscription(context.bot, user_id)
            if not is_subscribed:
                keyboard = [[KeyboardButton(f"Подписаться на {self.channel_username}")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(
                    f"Хей~ Чтобы отправлять мне фотографии, подпишись на канал {self.channel_username} 💙",
                    reply_markup=reply_markup
                )
                return

            media_group_id = update.message.media_group_id
            
            if media_group_id:
                await self._handle_media_group(update, context, user_id, media_group_id)
            else:
                await self._handle_single_photo(update, context, user_id)
                
        except Exception as e:
            print(f"Error in photo handling: {e}")
            await update.message.reply_text("Произошла ошибка при обработке фотографии...")

    async def _check_subscription(self, bot, user_id):
        """
        Проверка подписки пользователя на канал
        """
        try:
            member = await bot.get_chat_member(chat_id=self.channel_username, user_id=user_id)
            return member.status in ['member', 'administrator', 'creator']
        except Exception as e:
            print(f"Error checking subscription: {e}")
            return False

    async def _handle_single_photo(self, update, context, user_id):
        """
        Обработка одиночной фотографии
        """
        try:
            photo = update.message.photo[-1]
            photo_file = await context.bot.get_file(photo.file_id)
            photo_bytes = await photo_file.download_as_bytearray()
            base64_image = base64.b64encode(photo_bytes).decode('utf-8')
            
            caption = update.message.caption if update.message.caption else "Опиши, что ты видишь на этом изображении, учитывая свой характер и настроение."
            
            response = await self._get_image_response(user_id, caption, [base64_image])
            
            # Проверка на неприемлемый контент
            if self._is_inappropriate_content(response):
                response = await self._generate_playful_response()
            
            keyboard = [[KeyboardButton("Очистить память")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(response, reply_markup=reply_markup)
            
        except Exception as e:
            print(f"Error in single photo handling: {e}")
            await update.message.reply_text("Извини, не удалось обработать фотографию...")

    async def _handle_media_group(self, update, context, user_id, media_group_id):
        """
        Обработка группы фотографий
        """
        try:
            if f'media_group_{media_group_id}' not in context.bot_data:
                context.bot_data[f'media_group_{media_group_id}'] = {
                    'images': [],
                    'timestamp': datetime.now(),
                    'processed': False
                }
            
            photo = update.message.photo[-1]
            photo_file = await context.bot.get_file(photo.file_id)
            photo_bytes = await photo_file.download_as_bytearray()
            base64_image = base64.b64encode(photo_bytes).decode('utf-8')
            
            context.bot_data[f'media_group_{media_group_id}']['images'].append(base64_image)
            
            await asyncio.sleep(0.5)
            
            current_time = datetime.now()
            group_time = context.bot_data[f'media_group_{media_group_id}']['timestamp']
            time_passed = (current_time - group_time).total_seconds()
            
            if time_passed >= 0.5 and not context.bot_data[f'media_group_{media_group_id}']['processed']:
                context.bot_data[f'media_group_{media_group_id}']['processed'] = True
                
                images = context.bot_data[f'media_group_{media_group_id}']['images']
                caption = update.message.caption if update.message.caption else "Опиши, что ты видишь на этих изображениях, учитывая свой характер и настроение."
                
                response = await self._get_image_response(user_id, caption, images)
                
                # Проверка на неприемлемый контент
                if self._is_inappropriate_content(response):
                    response = await self._generate_playful_response()
                
                keyboard = [[KeyboardButton("Очистить память")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(response, reply_markup=reply_markup)
                
                del context.bot_data[f'media_group_{media_group_id}']
                
        except Exception as e:
            print(f"Error in media group handling: {e}")
            if f'media_group_{media_group_id}' in context.bot_data:
                del context.bot_data[f'media_group_{media_group_id}']
            await update.message.reply_text("Извини, не удалось обработать группу фотографий...")

    async def _get_image_response(self, user_id, text, images):
        """
        Получение ответа от GPT на изображение(я)
        """
        try:
            system_prompt = self.mood_manager.get_system_prompt(user_id)
            history = self.db.get_conversation_history(user_id)
            
            messages = [{"role": "system", "content": system_prompt}]
            for msg, role in history:
                messages.append({"role": role, "content": msg})
            
            content = [{"type": "text", "text": text}]
            for image in images:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image}"
                    }
                })
            
            messages.append({"role": "user", "content": content})
            
            response = self.client.chat.completions.create(
                model=self.GPT_MODEL,
                messages=messages,
                max_tokens=self.GPT_MAX_TOKENS,
                temperature=self.GPT_TEMPERATURE
            )
            
            bot_response = response.choices[0].message.content
            
            sentiment_score = self.mood_manager.analyze_sentiment(text)
            self.mood_manager.update_mood(user_id, sentiment_score)
            
            self.db.store_message(user_id, text, 'user')
            self.db.store_message(user_id, bot_response, 'assistant')
            
            return bot_response
            
        except Exception as e:
            print(f"Error in getting GPT response: {e}")
            return "Извини, произошла ошибка при обработке изображения..."