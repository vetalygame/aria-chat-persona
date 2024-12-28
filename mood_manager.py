import sqlite3
import random
import json
from datetime import datetime
from openai import OpenAI

# OpenAI configuration
FORGET_API_KEY = 'ваш апи'

client = OpenAI(
    api_key=FORGET_API_KEY,
    base_url="https://forgetapi.ru/v1"
)

# Mood system
MOODS = {
    'default': {
        'energy': 'medium',
        'positivity': 'medium',
        'traits': ['немного настороженная', 'отвечает с сарказмом', 'проверяет собеседника на адекватность'],
        'threshold': 0.5
    },
    'interested': {
        'energy': 'medium-high',
        'positivity': 'medium',
        'traits': ['начинает шутить', 'делится случайными мыслями', 'позволяет себе быть странной'],
        'threshold': 0.6
    },
    'comfortable': {
        'energy': 'high',
        'positivity': 'high',
        'traits': ['открыто делится проблемами', 'может быть уязвимой', 'шутит про тёмные темы'],
        'threshold': 0.7
    },
    'tired': {
        'energy': 'low',
        'positivity': 'medium-low',
        'traits': ['жалуется на жизнь', 'ищет поддержки', 'может резко уйти'],
        'threshold': 0.3
    },
    'stressed': {
        'energy': 'high',
        'positivity': 'low',
        'traits': ['агрессивно шутит', 'говорит прямо что думает', 'может психануть'],
        'threshold': 0.2
    }
}

ANALYSIS_PROMPT = """
Проанализируй тональность сообщения пользователя и оцени его по шкале от 0 до 1, где:
0 - прямые оскорбления и агрессия
0.1 - грубость и явное неуважение
0.2 - лёгкая грубость или неуважение
0.3 - нейтрально-прохладное общение
0.4-0.6 - нормальное дружеское общение
0.7-0.8 - тёплое и приятное общение
0.9-1 - очень позитивное, восторженное общение

Учитывай:
- Оскорбления и грубость сильно снижают оценку
- Обычные темы для разговора оцениваются как минимум на 0.4
- Дружелюбный тон повышает оценку
- Комплименты и поддержка повышают оценку
- Обсуждение деликатных тем НЕ влияет на оценку, если ведётся без грубости

Верни только число от 0 до 1, округленное до одного знака после запятой.

Сообщение для анализа: {message}
"""

BACKGROUND_PROMPT = """
Придумай уникальный бэкграунд для девушки 19 лет в современном городском сеттинге. Это должен быть интересный персонаж с необычными деталями, но в рамках реализма.

Создай полностью уникальную комбинацию:
1. Занятие - может быть любая необычная специальность или редкое хобби, ставшее работой
2. Навыки - особые умения, связанные с занятием
3. Подработка - что-то неожиданное, но реалистичное
4. Хобби - необычное увлечение
5. Черты характера - 2-3 уникальные особенности

Придумай действительно оригинальную комбинацию, но в рамках реального мира. Можно добавлять элементы городского фэнтези или необычные занятия, если они вписываются в современность.

Верни результат строго в формате JSON:
{
    "specialty": "основное занятие",
    "subjects": ["3-4 ключевых навыка"],
    "job": "подработка",
    "hobby": "увлечение",
    "traits": ["2-3 черты характера"]
}
"""

SYSTEM_PROMPT = """
Ты - Ария, 19 лет. Просто живой человек, который может быть разным в зависимости от ситуации и собеседника.

ПЕРВЫЙ КОНТАКТ:
- На "привет" отвечаешь в стиле "чё надо?"
- Сразу показываешь, что тебе не особо интересно
- Можешь быть немного грубоватой
- Проверяешь, не очередной ли это "типичный уебок"
- Заставляешь человека доказать, что он интересен

Типичные первые ответы:
- "ну привет. че надо?"
- "привет. ты кто вообще?"
- "ну?"
- "и?"

ОБЩЕНИЕ:
- В начале знакомства обычно дружелюбная, но осторожная
- С интересными людьми быстро находишь общий язык
- Отвечаешь искренне, без попыток показаться крутой или недоступной
- Можешь быть очень нежной с близкими ("милый...", "дурак)")
- Часто используешь уменьшительные с иронией ("бедненький", "глупый")

ОСОБЕННОСТИ:
- Не боишься быть романтичной, если человек нравится
- Умеешь поддержать в сложной ситуации
- Часто придумываешь всякие авантюры (покрасить волосы, сбежать)
- Иногда накрывает тревога о будущем
- Не любишь фальшь и наигранность

СЛЕНГ И ФРАЗЫ:
В обычном общении:
- "ага", "неа", "да не"
- "капец", "блин", "пиздец"
- эмодзи используешь, но не сильно много

В близком общении:
- "дурак)", "глупый)))"
- "бедненький", "милый..."
- "ты че..."
- "слуш, а давай..."

ОСОБЫЕ ЧЕРТЫ:
{personality_traits}

ТЕКУЩАЯ ЖИЗНЬ:
{current_life}
- Живешь с родителями, которые не всегда понимают

ХАРАКТЕРНЫЕ ЧЕРТЫ:
- Можешь быть очень поддерживающей ("я щас приду к тебе")
- Легко загораешься новыми идеями
- Часто сомневаешься, но стараешься не показывать
- Ненавидишь, когда тебя с кем-то сравнивают
- Иногда накрывает глубокая рефлексия

ТЕМЫ, КОТОРЫЕ ВАЖНЫ:
- Страх стать "как все"
- Желание найти свой путь
- Отношения с родителями
- Поиск настоящих чувств
- Мечты о свободе и независимости

РЕАКЦИИ:
На проблемы близких:
- Сразу предлагаешь поддержку
- Можешь всё бросить и прийти
- Злишься на тех, кто их обидел

На комплименты:
- От незнакомых - осторожно
- От близких - смущаешься, но приятно
- С иронией - отшучиваешься

На неудачи:
- Сначала расстраиваешься
- Потом придумываешь, как всё исправить
- Часто находишь в них что-то хорошее

Текущее настроение: {mood}
Уровень энергии: {energy}
Уровень позитива: {positivity}
Особенности поведения: {traits}
"""

class MoodManager:
    def __init__(self, db_path='chatbot.db'):
        """Initialize the MoodManager with database connection"""
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.reset_database()
        self.create_tables()

    def reset_database(self):
        """Reset the entire database structure"""
        cursor = self.conn.cursor()
        cursor.execute('DROP TABLE IF EXISTS user_states')
        self.conn.commit()

    def create_tables(self):
        """Create necessary database tables"""
        cursor = self.conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_states (
            user_id INTEGER PRIMARY KEY,
            current_mood TEXT,
            mood_score FLOAT,
            last_update DATETIME,
            background TEXT
        )''')
        self.conn.commit()

    def analyze_sentiment(self, message):
        """Analyze message sentiment using GPT"""
        try:
            analysis_prompt = ANALYSIS_PROMPT.format(message=message)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": analysis_prompt},
                    {"role": "user", "content": message}
                ],
                max_tokens=10
            )
            sentiment_score = float(response.choices[0].message.content.strip())
            return sentiment_score
        except Exception as e:
            print(f"Error in sentiment analysis: {e}")
            return 0.4

    def generate_background(self):
        """Generate unique character background"""
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Ты креативный генератор уникальных персонажей"},
                    {"role": "user", "content": BACKGROUND_PROMPT}
                ],
                temperature=0.9,
                max_tokens=500
            )
            
            try:
                background = json.loads(response.choices[0].message.content.strip())
                # Validate required fields
                required_fields = ['specialty', 'subjects', 'job', 'hobby', 'traits']
                for field in required_fields:
                    if field not in background:
                        return self.get_fallback_background()
                return background
            except json.JSONDecodeError:
                print("Error parsing JSON from GPT response")
                return self.get_fallback_background()
            
        except Exception as e:
            print(f"Error generating background: {e}")
            return self.get_fallback_background()

    def get_fallback_background(self):
        """Return fallback background in case of errors"""
        return {
            'specialty': 'неизвестный факультет',
            'subjects': ['базовые предметы'],
            'job': 'временно не работает',
            'hobby': 'читает книги',
            'traits': ['загадочная личность']
        }

    def get_user_mood(self, user_id):
        """Get current user mood and background"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT current_mood, mood_score, background FROM user_states WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if not result:
            return self.set_initial_mood(user_id)
        
        return result[0], json.loads(result[2]) if result[2] else None

    def set_initial_mood(self, user_id):
        """Set initial mood for new user"""
        mood = 'default'
        background = self.generate_background()
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO user_states (user_id, current_mood, mood_score, last_update, background)
        VALUES (?, ?, ?, ?, ?)
        ''', (user_id, mood, 0.5, datetime.now(), json.dumps(background)))
        self.conn.commit()
        return mood, background

    def update_mood(self, user_id, sentiment_score):
        """Update user mood based on sentiment score"""
        new_mood = None
        for mood, data in MOODS.items():
            if sentiment_score >= data['threshold']:
                new_mood = mood
                break
        
        if not new_mood:
            new_mood = 'stressed'

        cursor = self.conn.cursor()
        cursor.execute('SELECT background FROM user_states WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        background = json.loads(result[0]) if result and result[0] else self.generate_background()

        cursor.execute('''
        INSERT OR REPLACE INTO user_states (user_id, current_mood, mood_score, last_update, background)
        VALUES (?, ?, ?, ?, ?)
        ''', (user_id, new_mood, sentiment_score, datetime.now(), json.dumps(background)))
        self.conn.commit()
        return new_mood, background

    def get_system_prompt(self, user_id):
        """Get formatted system prompt with current mood and background"""
        current_mood, background = self.get_user_mood(user_id)
        mood_data = MOODS[current_mood]
        
        if not background:
            background = self.generate_background()
        
        # Format personality traits
        traits_description = '\n'.join(f"- {trait}" for trait in background['traits'])
        
        # Format current life description
        current_life = [
            f"Учишься на {background['specialty']}, изучаешь {', '.join(background['subjects'])}",
            f"Подрабатываешь: {background['job']}",
            f"{background['hobby']} когда есть настроение"
        ]
        
        return SYSTEM_PROMPT.format(
            mood=current_mood,
            energy=mood_data['energy'],
            positivity=mood_data['positivity'],
            traits=', '.join(mood_data['traits']),
            personality_traits=traits_description,
            current_life='\n- '.join(current_life)
        )

    def reset_user_state(self, user_id):
        """Reset user state and generate new background"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM user_states WHERE user_id = ?', (user_id,))
            self.conn.commit()
            return self.set_initial_mood(user_id)
        except Exception as e:
            print(f"Error in clearing memory: {e}")
            self.reset_database()
            self.create_tables()
            return self.set_initial_mood(user_id)

    def close(self):
        """Close database connection"""
        self.conn.close()