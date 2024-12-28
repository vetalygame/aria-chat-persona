class TimeManager:
    def __init__(self, db_manager):
        self.db = db_manager
        self.user_activities = {}  # Хранение временных меток и активностей пользователей

    def get_current_time(self):
        """Получение текущего времени"""
        return datetime.now()

    def store_user_activity(self, user_id, activity_type, details=None):
        """Сохранение активности пользователя"""
        current_time = self.get_current_time()
        if user_id not in self.user_activities:
            self.user_activities[user_id] = []
        
        self.user_activities[user_id].append({
            'type': activity_type,
            'time': current_time,
            'details': details
        })

    def get_time_since_last_interaction(self, user_id, activity_type=None):
        """Получение времени с последней активности определенного типа"""
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
        """Извлечение упоминаний о времени из сообщения"""
        # Здесь можно использовать регулярные выражения или NLP
        # для поиска упоминаний о времени и планах
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
        """Форматирование разницы во времени в читаемый вид"""
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
