import os
import json
import shutil
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
import zipfile
import io

class ExtensionManager:
    def __init__(self, additions_path):
        self.additions_path = additions_path
        self.additions_list_path = os.path.join(additions_path, 'additions_list.json')
        self.server = None
        self.server_thread = None
        
    def load_additions_list(self):
        """Загружает список расширений"""
        if os.path.exists(self.additions_list_path):
            with open(self.additions_list_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_additions_list(self, additions_list):
        """Сохраняет список расширений"""
        with open(self.additions_list_path, 'w', encoding='utf-8') as f:
            json.dump(additions_list, f, ensure_ascii=False, indent=2)
    
    def get_installed_extensions(self):
        """Возвращает список установленных расширений"""
        additions_list = self.load_additions_list()
        installed = []
        
        for name, path in additions_list.items():
            extension_path = os.path.join(self.additions_path, path)
            rules_file = os.path.join(extension_path, 'rules.json')
            
            if os.path.exists(rules_file):
                try:
                    with open(rules_file, 'r', encoding='utf-8') as f:
                        rules = json.load(f)
                    
                    installed.append({
                        'name': name,
                        'path': path,
                        'description': rules.get('description', 'Нет описания'),
                        'version': rules.get('version', 'Неизвестно'),
                        'based_on': rules.get('based_on', ''),
                        'running': False  # Можно добавить проверку статуса
                    })
                except:
                    installed.append({
                        'name': name,
                        'path': path,
                        'description': 'Ошибка загрузки',
                        'version': 'Неизвестно',
                        'based_on': '',
                        'running': False
                    })
        
        return installed
    
    def download_extension(self, name, github_url):
        """Скачивает и устанавливает расширение"""
        try:
            # Скачиваем архив
            response = requests.get(github_url)
            response.raise_for_status()
            
            # Создаем папку для расширения
            extension_dir = os.path.join(self.additions_path, name)
            if os.path.exists(extension_dir):
                shutil.rmtree(extension_dir)
            os.makedirs(extension_dir, exist_ok=True)
            
            # Распаковываем архив
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                zip_ref.extractall(extension_dir)
            
            # Добавляем в additions_list.json
            additions_list = self.load_additions_list()
            additions_list[name] = f"{name}/"
            self.save_additions_list(additions_list)
            
            return True, "Расширение успешно установлено!"
            
        except Exception as e:
            return False, f"Ошибка установки: {str(e)}"
    
    def delete_extension(self, name):
        """Удаляет расширение"""
        try:
            additions_list = self.load_additions_list()
            
            if name in additions_list:
                # Удаляем папку расширения
                extension_path = os.path.join(self.additions_path, additions_list[name])
                if os.path.exists(extension_path):
                    shutil.rmtree(extension_path)
                
                # Удаляем из списка
                del additions_list[name]
                self.save_additions_list(additions_list)
                
                return True, "Расширение успешно удалено!"
            else:
                return False, "Расширение не найдено!"
                
        except Exception as e:
            return False, f"Ошибка удаления: {str(e)}"
    
    def start_server(self):
        """Запускает HTTP сервер"""
        class ExtensionHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=os.path.dirname(__file__), **kwargs)
            
            def do_GET(self):
                if self.path == '/':
                    self.path = '/manager.html'
                elif self.path.startswith('/api/'):
                    self.handle_api()
                    return
                return super().do_GET()
            
            def handle_api(self):
                if self.path == '/api/extensions':
                    self.send_json(manager.get_installed_extensions())
                
                elif self.path == '/api/remote':
                    # Здесь можно добавить загрузку удаленного списка
                    remote_extensions = {
                        "Weather App": {
                            "url": "https://github.com/example/weather-extension/archive/main.zip",
                            "description": "Погодное приложение",
                            "version": "1.0.0"
                        },
                        "Notes": {
                            "url": "https://github.com/example/notes-extension/archive/main.zip",
                            "description": "Приложение для заметок",
                            "version": "1.0.0"
                        }
                    }
                    self.send_json(remote_extensions)
                
                elif self.path.startswith('/api/install/'):
                    params = parse_qs(urlparse(self.path).query)
                    name = self.path.split('/')[-1]
                    url = params.get('url', [''])[0]
                    
                    if url:
                        success, message = manager.download_extension(name, url)
                        self.send_json({'success': success, 'message': message})
                    else:
                        self.send_json({'success': False, 'message': 'URL не указан'})
                
                elif self.path.startswith('/api/delete/'):
                    name = self.path.split('/')[-1]
                    success, message = manager.delete_extension(name)
                    self.send_json({'success': success, 'message': message})
            
            def send_json(self, data):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode('utf-8'))
        
        # Создаем и запускаем сервер в отдельном потоке
        self.server = HTTPServer(('localhost', 5000), ExtensionHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        print("Extension manager server started on http://localhost:5000")
    
    def stop_server(self):
        """Останавливает сервер"""
        if self.server:
            self.server.shutdown()
            self.server_thread.join()

# Глобальный экземпляр менеджера
manager = None

def main():
    global manager
    # Получаем путь к additions из переменной окружения или используем текущую директорию
    additions_path = os.environ.get('ADDITIONS_PATH', os.path.join(os.path.dirname(__file__), '..'))
    additions_path = os.path.abspath(additions_path)
    
    manager = ExtensionManager(additions_path)
    manager.start_server()
    
    try:
        # Бесконечный цикл для поддержания работы сервера
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.stop_server()

if __name__ == "__main__":
    main()
