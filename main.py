import sys
import os
import json
import subprocess
from pathlib import Path
from PySide6.QtCore import QUrl, Qt, QSize, QPropertyAnimation, QEasingCurve, QProcess, Signal,QProcessEnvironment
from PySide6.QtWidgets import (QApplication, QMainWindow, QLineEdit, QToolBar, 
                               QPushButton, QWidget, QVBoxLayout, QHBoxLayout, 
                               QFrame, QLabel, QTabWidget, QStyle, QScrollArea,
                               QTextEdit, QSplitter, QSizePolicy, QMenu, QDialog,
                               QDialogButtonBox, QFormLayout, QComboBox)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtGui import QIcon, QPalette, QColor, QFont, QAction, QKeySequence

class ServerMonitorDialog(QDialog):
    def __init__(self, process, parent=None):
        super().__init__(parent)
        self.process = process
        self.setWindowTitle("Монитор сервера")
        self.setGeometry(200, 200, 800, 500)
        
        layout = QVBoxLayout(self)
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                font-family: 'Courier New';
                font-size: 12px;
                border: 1px solid #444;
            }
        """)
        
        layout.addWidget(self.output_text)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Подключаем вывод процесса
        if self.process:
            self.process.readyReadStandardOutput.connect(self.read_output)
            self.process.readyReadStandardError.connect(self.read_error)
    
    def read_output(self):
        data = self.process.readAllStandardOutput().data().decode()
        self.output_text.append(data)
    
    def read_error(self):
        data = self.process.readAllStandardError().data().decode()
        self.output_text.append(f"<font color='red'>{data}</font>")

class ExtensionManager:
    def __init__(self, browser):
        self.browser = browser
        self.additions_path = self.get_additions_path()
        self.extensions = {}
        self.processes = {}
        self.load_extensions()
    
    def get_additions_path(self):
        """Возвращает абсолютный путь к папке additions"""
        script_dir = Path(__file__).parent.absolute()
        additions_path = script_dir / "additions"
        return str(additions_path)
    
    def load_extensions(self):
        """Загружает список расширений из additions_list.json"""
        try:
            additions_file = os.path.join(self.additions_path, "additions_list.json")
            if os.path.exists(additions_file):
                with open(additions_file, 'r', encoding='utf-8') as f:
                    additions_data = json.load(f)
                
                for name, path in additions_data.items():
                    extension_path = os.path.join(self.additions_path, path)
                    rules_file = os.path.join(extension_path, "rules.json")
                    
                    if os.path.exists(rules_file):
                        with open(rules_file, 'r', encoding='utf-8') as f:
                            rules = json.load(f)
                        
                        self.extensions[name] = {
                            'path': extension_path,
                            'rules': rules,
                            'running': False
                        }
        except Exception as e:
            print(f"Ошибка загрузки расширений: {e}")
    
    def get_extension_info(self, name):
        """Возвращает информацию о расширении"""
        if name in self.extensions:
            ext = self.extensions[name]
            rules = ext['rules']
            return {
                'name': name,
                'description': rules.get('description', 'Нет описания'),
                'version': rules.get('version', 'Неизвестно'),
                'logo': rules.get('logo', ''),
                'running': ext['running']
            }
        return None
    
    def run_extension(self, name):
        """Запускает расширение"""
        if name in self.extensions and not self.extensions[name]['running']:
            ext = self.extensions[name]
            rules = ext['rules']
            
            try:
                if rules.get('based_on') == 'python':
                    # Запуск Python скрипта
                    script_path = os.path.join(ext['path'], rules.get('start', 'app.py'))
                    if not os.path.exists(script_path):
                        print(f"Файл не найден: {script_path}")
                        return None
                    
                    process = QProcess()
                    process.setWorkingDirectory(ext['path'])
                    
                    # Устанавливаем переменные окружения
                    env = QProcessEnvironment.systemEnvironment()
                    env.insert("ADDITIONS_PATH", self.additions_path)
                    process.setProcessEnvironment(env)
                    
                    process.start('python', [script_path])
                    
                    self.processes[name] = process
                    self.extensions[name]['running'] = True
                    
                    # Если есть ссылка, открываем ее
                    link = rules.get('link')
                    if link:
                        self.browser.add_new_tab(QUrl(link), name)
                    
                    return process
                
                elif rules.get('based_on') == 'html':
                    # Открываем HTML файл
                    html_path = os.path.join(ext['path'], rules.get('start', 'index.html'))
                    if not os.path.exists(html_path):
                        print(f"Файл не найден: {html_path}")
                        return None
                    
                    # Используем абсолютный путь для file://
                    absolute_html_path = os.path.abspath(html_path)
                    url = QUrl.fromLocalFile(absolute_html_path)
                    self.browser.add_new_tab(url, name)
                    self.extensions[name]['running'] = True
                    return True
                
                elif rules.get('based_on') == 'exe':
                    # Запуск исполняемого файла
                    exe_path = os.path.join(ext['path'], rules.get('start'))
                    if not os.path.exists(exe_path):
                        print(f"Файл не найден: {exe_path}")
                        return None
                    
                    process = QProcess()
                    process.setWorkingDirectory(ext['path'])
                    process.start(exe_path)
                    
                    self.processes[name] = process
                    self.extensions[name]['running'] = True
                    
                    # Если есть ссылка, открываем ее
                    link = rules.get('link')
                    if link:
                        self.browser.add_new_tab(QUrl(link), name)
                    
                    return process
                
                elif rules.get('based_on') == 'url':
                    # Просто открываем URL
                    url = rules.get('start')
                    if url:
                        self.browser.add_new_tab(QUrl(url), name)
                        self.extensions[name]['running'] = True
                        return True
                    else:
                        print(f"URL не указан для расширения {name}")
                        return None
                
                else:
                    print(f"Неизвестный тип расширения: {rules.get('based_on')}")
                    return None
                
            except Exception as e:
                print(f"Ошибка запуска расширения {name}: {e}")
                return None
        
        elif name in self.extensions and self.extensions[name]['running']:
            print(f"Расширение {name} уже запущено")
            # Если уже запущено, но нужно открыть вкладку
            ext = self.extensions[name]
            rules = ext['rules']
            link = rules.get('link')
            if link:
                self.browser.add_new_tab(QUrl(link), name)
            return self.processes.get(name, True)
        
        else:
            print(f"Расширение {name} не найдено")
            return None
    
    def stop_extension(self, name):
        """Останавливает расширение"""
        if name in self.processes:
            process = self.processes[name]
            process.terminate()
            process.waitForFinished(1000)
            if process.state() == QProcess.Running:
                process.kill()
            
            del self.processes[name]
            self.extensions[name]['running'] = False
            return True
        return False

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Офлайн Браузер")
        self.setGeometry(100, 100, 1400, 900)
        
        # Получаем абсолютный путь к директории скрипта
        self.script_dir = Path(__file__).parent.absolute()
        
        # Менеджер расширений
        self.extension_manager = ExtensionManager(self)
        
        # Устанавливаем темную тему
        self.set_dark_theme()
        
        # Флаг открытого меню
        self.menu_expanded = False
        
        # Главный виджет и layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Боковое меню (слева)
        self.menu_frame = QFrame()
        self.menu_frame.setFixedWidth(60)  # Свернутое состояние
        self.menu_frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border: none;
            }
        """)
        
        # Контент меню
        menu_layout = QVBoxLayout(self.menu_frame)
        menu_layout.setSpacing(10)
        menu_layout.setContentsMargins(5, 10, 5, 10)
        
        # Кнопка меню
        self.menu_btn = QPushButton("☰")
        self.menu_btn.setFixedSize(40, 40)
        self.menu_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
            QPushButton:pressed {
                background-color: #4d4d4d;
            }
        """)
        self.menu_btn.clicked.connect(self.toggle_menu)
        menu_layout.addWidget(self.menu_btn)
        
        # Список расширений
        self.extensions_scroll = QScrollArea()
        self.extensions_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #252525;
                border-radius: 8px;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: #252525;
            }
        """)
        self.extensions_scroll.setWidgetResizable(True)
        
        self.extensions_widget = QWidget()
        self.extensions_layout = QVBoxLayout(self.extensions_widget)
        self.extensions_layout.setSpacing(5)
        
        self.extensions_scroll.setWidget(self.extensions_widget)
        menu_layout.addWidget(self.extensions_scroll)
        
        # Обновляем список расширений
        self.update_extensions_list()
        
        # Кнопки внизу меню
        menu_bottom_widget = QWidget()
        menu_bottom_layout = QVBoxLayout(menu_bottom_widget)
        menu_bottom_layout.setSpacing(5)
        
        # Кнопка настроек
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(40, 40)
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
        """)
        settings_btn.setToolTip("Настройки")
        menu_bottom_layout.addWidget(settings_btn)
        
        # Кнопка расширений
        extensions_btn = QPushButton("🧩")
        extensions_btn.setFixedSize(40, 40)
        extensions_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
        """)
        extensions_btn.setToolTip("Управление расширениями")
        extensions_btn.clicked.connect(lambda: self.extension_manager.run_extension("Extension Manager"))
        menu_bottom_layout.addWidget(extensions_btn)
        
        menu_layout.addStretch()
        menu_layout.addWidget(menu_bottom_widget)
        
        # Правая часть (браузер)
        browser_widget = QWidget()
        browser_layout = QVBoxLayout(browser_widget)
        browser_layout.setSpacing(0)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        
        # Панель навигации
        navbar = QToolBar()
        navbar.setStyleSheet("""
            QToolBar {
                background-color: #252525;
                border: none;
                padding: 5px;
                spacing: 5px;
            }
        """)
        navbar.setFixedHeight(50)
        
        # Кнопка назад
        back_btn = QPushButton()
        back_btn.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        back_btn.setStyleSheet(self.get_toolbar_button_style())
        back_btn.clicked.connect(self.navigate_back)
        navbar.addWidget(back_btn)
        
        # Кнопка вперед
        forward_btn = QPushButton()
        forward_btn.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        forward_btn.setStyleSheet(self.get_toolbar_button_style())
        forward_btn.clicked.connect(self.navigate_forward)
        navbar.addWidget(forward_btn)
        
        # Кнопка обновить
        reload_btn = QPushButton()
        reload_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        reload_btn.setStyleSheet(self.get_toolbar_button_style())
        reload_btn.clicked.connect(self.navigate_reload)
        navbar.addWidget(reload_btn)
        
        # Поле для ввода пути к файлу
        self.url_bar = QLineEdit()
        self.url_bar.setStyleSheet("""
            QLineEdit {
                border: 1px solid #444;
                border-radius: 20px;
                padding: 8px 15px;
                background-color: #2d2d2d;
                color: white;
                font-size: 14px;
                selection-background-color: #3a3a3a;
            }
            QLineEdit:focus {
                border: 1px solid #555;
                background-color: #333;
            }
        """)
        self.url_bar.setPlaceholderText("Введите URL или путь к файлу...")
        self.url_bar.returnPressed.connect(self.navigate_to_file)
        navbar.addWidget(self.url_bar)
        
        # Кнопка новой вкладки
        new_tab_btn = QPushButton("+")
        new_tab_btn.setStyleSheet(self.get_toolbar_button_style())
        new_tab_btn.setFixedSize(30, 30)
        new_tab_btn.clicked.connect(lambda: self.add_new_tab())
        navbar.addWidget(new_tab_btn)
        
        browser_layout.addWidget(navbar)
        
        # Создаем вкладки
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBarDoubleClicked.connect(self.tab_double_click)
        self.tabs.currentChanged.connect(self.current_tab_changed)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_current_tab)
        
        # Стиль для вкладок
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #ccc;
                padding: 8px 15px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                border: none;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: white;
                border-bottom: 2px solid #4a8cff;
            }
            QTabBar::tab:hover:!selected {
                background-color: #3d3d3d;
            }
            QTabBar::close-button {
                image: url(close.png);
                subcontrol-position: right;
            }
            QTabBar::close-button:hover {
                background-color: #e81123;
                border-radius: 8px;
            }
        """)
        
        browser_layout.addWidget(self.tabs)
        
        # Добавляем меню и браузер в главный layout
        main_layout.addWidget(self.menu_frame)
        main_layout.addWidget(browser_widget, 1)
        
        # Добавляем первую вкладку
        self.add_new_tab(QUrl.fromLocalFile(''), 'Новая вкладка')
        
        # Анимация для меню
        self.menu_animation = QPropertyAnimation(self.menu_frame, b"minimumWidth")
        self.menu_animation.setEasingCurve(QEasingCurve.InOutQuart)
        self.menu_animation.setDuration(300)
        
        # Настройка горячих клавиш
        self.setup_shortcuts()
    
    def setup_shortcuts(self):
        """Настройка горячих клавиш"""
        # F11 - монитор сервера
        f11_action = QAction(self)
        f11_action.setShortcut(QKeySequence("F11"))
        f11_action.triggered.connect(self.show_server_monitor)
        self.addAction(f11_action)
    
    def get_toolbar_button_style(self):
        return """
            QPushButton {
                background-color: #3d3d3d;
                border: none;
                border-radius: 8px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:pressed {
                background-color: #5d5d5d;
            }
        """
    
    def set_dark_theme(self):
        # Устанавливаем темную палитру для всего приложения
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(30, 30, 30))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(35, 35, 35))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        
        self.setPalette(dark_palette)
        
        # Дополнительные стили для темной темы
        self.setStyleSheet("""
            QMainWindow, QDialog {
                background-color: #1e1e1e;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #2d2d2d;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #4d4d4d;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5d5d5d;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
    
    def update_extensions_list(self):
        """Обновляет список расширений в боковой панели"""
        # Очищаем текущий список
        for i in reversed(range(self.extensions_layout.count())):
            widget = self.extensions_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Добавляем расширения
        for name in self.extension_manager.extensions.keys():
            ext_info = self.extension_manager.get_extension_info(name)
            if ext_info:
                self.add_extension_widget(ext_info)
        
        # Добавляем растяжку
        self.extensions_layout.addStretch()
    
    def add_extension_widget(self, ext_info):
        """Добавляет виджет расширения в список"""
        ext_frame = QFrame()
        ext_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 6px;
                padding: 5px;
            }
            QFrame:hover {
                background-color: #3d3d3d;
            }
        """)
        ext_frame.setFixedHeight(60)
        
        layout = QHBoxLayout(ext_frame)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Логотип (заглушка)
        logo_label = QLabel("📦")
        logo_label.setFixedSize(30, 30)
        layout.addWidget(logo_label)
        
        # Информация
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        name_label = QLabel(ext_info['name'])
        name_label.setStyleSheet("color: white; font-weight: bold;")
        info_layout.addWidget(name_label)
        
        desc_label = QLabel(ext_info['description'][:20] + "...")
        desc_label.setStyleSheet("color: #ccc; font-size: 10px;")
        info_layout.addWidget(desc_label)
        
        layout.addWidget(info_widget)
        
        # Кнопка запуска
        run_btn = QPushButton("▶" if not ext_info['running'] else "⏹")
        run_btn.setFixedSize(30, 30)
        run_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        run_btn.clicked.connect(lambda: self.toggle_extension(ext_info['name'], run_btn))
        layout.addWidget(run_btn)
        
        self.extensions_layout.addWidget(ext_frame)
    
    def toggle_extension(self, name, button):
        """Запускает/останавливает расширение"""
        ext = self.extension_manager.extensions[name]
        
        if ext['running']:
            # Останавливаем
            if self.extension_manager.stop_extension(name):
                button.setText("▶")
        else:
            # Запускаем
            process = self.extension_manager.run_extension(name)
            if process:
                button.setText("⏹")
                # Если это Python процесс, запоминаем его для монитора
                if isinstance(process, QProcess):
                    ext['process'] = process
        
        self.update_extensions_list()
    
    def show_extensions_manager(self):
        """Показывает диалог управления расширениями"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Управление расширениями")
        dialog.setGeometry(150, 150, 600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Таблица с расширениями
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        
        for name, ext in self.extension_manager.extensions.items():
            ext_frame = QFrame()
            ext_frame.setStyleSheet("""
                QFrame {
                    background-color: #2d2d2d;
                    border-radius: 8px;
                    padding: 10px;
                    margin: 5px;
                }
            """)
            
            frame_layout = QHBoxLayout(ext_frame)
            
            # Информация
            info_widget = QWidget()
            info_layout = QVBoxLayout(info_widget)
            
            name_label = QLabel(f"<b>{name}</b>")
            name_label.setStyleSheet("color: white;")
            info_layout.addWidget(name_label)
            
            desc_label = QLabel(ext['rules'].get('description', 'Нет описания'))
            desc_label.setStyleSheet("color: #ccc;")
            info_layout.addWidget(desc_label)
            
            version_label = QLabel(f"Версия: {ext['rules'].get('version', 'Неизвестно')}")
            version_label.setStyleSheet("color: #999; font-size: 10px;")
            info_layout.addWidget(version_label)
            
            frame_layout.addWidget(info_widget)
            
            # Статус
            status_label = QLabel("Запущено" if ext['running'] else "Остановлено")
            status_label.setStyleSheet("color: #4CAF50;" if ext['running'] else "color: #f44336;")
            frame_layout.addWidget(status_label)
            
            content_layout.addWidget(ext_frame)
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        dialog.exec()
    
    def show_server_monitor(self):
        """Показывает монитор сервера"""
        # Ищем запущенные Python процессы
        running_processes = []
        for name, ext in self.extension_manager.extensions.items():
            if ext['running'] and 'process' in ext:
                running_processes.append((name, ext['process']))
        
        if running_processes:
            # Если есть процессы, показываем диалог выбора
            dialog = QDialog(self)
            dialog.setWindowTitle("Выбор сервера для мониторинга")
            dialog.setGeometry(200, 200, 400, 200)
            
            layout = QVBoxLayout(dialog)
            
            form_layout = QFormLayout()
            combo = QComboBox()
            for name, process in running_processes:
                combo.addItem(name, process)
            
            form_layout.addRow("Выберите сервер:", combo)
            layout.addLayout(form_layout)
            
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(lambda: self.open_monitor(combo.currentData(), dialog))
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            dialog.exec()
        else:
            # Если нет процессов, показываем пустой монитор
            monitor = ServerMonitorDialog(None, self)
            monitor.exec()
    
    def open_monitor(self, process, dialog):
        """Открывает монитор для выбранного процесса"""
        dialog.accept()
        monitor = ServerMonitorDialog(process, self)
        monitor.exec()
    
    def add_new_tab(self, qurl=None, label="Новая вкладка"):
        if qurl is None:
            qurl = QUrl.fromLocalFile('')
            
        browser = QWebEngineView()
        browser.setUrl(qurl)
        
        i = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(i)
        
        # Обновляем URL бар при изменении URL
        browser.urlChanged.connect(lambda qurl, browser=browser: 
            self.update_urlbar(qurl, browser))
            
        # Обновляем заголовок вкладки при изменении заголовка страницы
        browser.loadFinished.connect(lambda _, i=i, browser=browser: 
            self.tabs.setTabText(i, browser.page().title()[:15] + "..."))
    
    def tab_double_click(self, i):
        if i == -1:  # Двойной клик на пустом пространстве
            self.add_new_tab()
    
    def current_tab_changed(self, i):
        if i >= 0:
            qurl = self.tabs.currentWidget().url()
            self.update_urlbar(qurl, self.tabs.currentWidget())
    
    def close_current_tab(self, i):
        if self.tabs.count() > 1:
            self.tabs.removeTab(i)
    
    def update_urlbar(self, qurl, browser=None):
        if browser != self.tabs.currentWidget():
            return
            
        if qurl.toString().startswith('file:///'):
            self.url_bar.setText(qurl.toString()[8:])  # Убираем префикс file:///
        else:
            self.url_bar.setText(qurl.toString())
    
    def navigate_to_file(self):
        file_path = self.url_bar.text()
        if not file_path:
            return
            
        # Если путь относительный, преобразуем в абсолютный
        if not os.path.isabs(file_path):
            file_path = os.path.join(str(self.script_dir), file_path)
        
        if os.path.exists(file_path) and file_path.endswith('.html'):
            # Для локальных файлов используем file:///
            url = QUrl.fromLocalFile(os.path.abspath(file_path))
            self.tabs.currentWidget().setUrl(url)
        else:
            # Можно также открывать обычные URL
            self.tabs.currentWidget().setUrl(QUrl(file_path))
    
    def navigate_back(self):
        self.tabs.currentWidget().back()
    
    def navigate_forward(self):
        self.tabs.currentWidget().forward()
    
    def navigate_reload(self):
        self.tabs.currentWidget().reload()
    
    def toggle_menu(self):
        if self.menu_expanded:
            self.menu_animation.setStartValue(250)
            self.menu_animation.setEndValue(60)
        else:
            self.menu_animation.setStartValue(60)
            self.menu_animation.setEndValue(250)
        
        self.menu_animation.start()
        self.menu_expanded = not self.menu_expanded

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Browser()
    window.show()
    sys.exit(app.exec_())