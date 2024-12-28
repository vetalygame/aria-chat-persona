import requests
import time

class VoiceHandler:
    def __init__(self, api_key):
        self.api_key = api_key
        
    def transcribe_audio(self, audio_file):
        """Преобразует аудио в текст"""
        upload_url = self._upload_audio(audio_file)
        if not upload_url:
            return None

        headers = {
            "authorization": self.api_key,
            "content-type": "application/json"
        }
        data = {
            "audio_url": upload_url,
            "language_code": "ru",
            "punctuate": True,
            "format_text": True
        }
        
        try:
            # Отправляем запрос на транскрипцию
            response = requests.post("https://api.assemblyai.com/v2/transcript", 
                                  json=data, 
                                  headers=headers)
            response.raise_for_status()  # Проверяем на ошибки
            transcript_id = response.json()['id']

            # Ждем результат
            while True:
                response = requests.get(
                    f"https://api.assemblyai.com/v2/transcript/{transcript_id}", 
                    headers=headers
                )
                result = response.json()
                
                if result['status'] == 'completed':
                    return result['text']
                elif result['status'] == 'error':
                    print(f"Ошибка транскрипции: {result.get('error', 'Unknown error')}")
                    return None
                    
                time.sleep(1)
                
        except Exception as e:
            print(f"Ошибка при транскрипции: {e}")
            return None

    def _upload_audio(self, audio_file):
        """Загружает аудиофайл на сервер AssemblyAI"""
        headers = {"authorization": self.api_key}
        try:
            response = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=headers,
                data=audio_file
            )
            response.raise_for_status()  # Проверяем на ошибки
            return response.json()["upload_url"]
        except Exception as e:
            print(f"Ошибка при загрузке аудио: {e}")
            return None
