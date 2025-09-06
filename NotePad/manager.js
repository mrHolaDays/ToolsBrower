class ExtensionManager {
    constructor() {
        this.apiBase = 'http://localhost:5000/api';
        this.initialize();
    }

    async initialize() {
        await this.loadInstalledExtensions();
        this.setupEventListeners();
    }

    async apiCall(endpoint) {
        try {
            const response = await fetch(`${this.apiBase}${endpoint}`);
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            this.showMessage('Ошибка соединения с сервером', 'error');
            return null;
        }
    }

    async loadInstalledExtensions() {
        const extensions = await this.apiCall('/extensions');
        if (extensions) {
            this.displayExtensions(extensions, 'installed-extensions', true);
        }
    }

    async loadRemoteExtensions() {
        const url = document.getElementById('github-url').value;
        if (!url) {
            this.showMessage('Введите URL JSON файла', 'error');
            return;
        }

        // Здесь можно реализовать загрузку с удаленного URL
        // Для примера используем встроенный список
        const extensions = await this.apiCall('/remote');
        if (extensions) {
            this.displayExtensions(extensions, 'available-extensions', false);
        }
    }

    displayExtensions(extensions, containerId, isInstalled) {
        const container = document.getElementById(containerId);
        
        if (extensions.length === 0 || Object.keys(extensions).length === 0) {
            container.innerHTML = '<div class="loading">Нет расширений</div>';
            return;
        }

        container.innerHTML = '';

        const extensionsArray = isInstalled ? extensions : Object.entries(extensions).map(([name, info]) => ({
            name,
            ...info
        }));

        extensionsArray.forEach(ext => {
            const card = this.createExtensionCard(ext, isInstalled);
            container.appendChild(card);
        });
    }

    createExtensionCard(ext, isInstalled) {
        const card = document.createElement('div');
        card.className = 'extension-card';
        
        card.innerHTML = `
            <div class="extension-header">
                <span class="extension-name">${ext.name}</span>
                ${isInstalled ? `<span class="extension-status">${ext.running ? '▶' : '⏹'}</span>` : ''}
            </div>
            <div class="extension-desc">${ext.description || 'Нет описания'}</div>
            <div class="extension-version">Версия: ${ext.version || 'Неизвестно'}</div>
            <div class="extension-based">Тип: ${ext.based_on || 'Неизвестно'}</div>
            <div class="extension-actions">
                ${isInstalled ? 
                    `<button class="delete" onclick="manager.deleteExtension('${ext.name}')">🗑️ Удалить</button>` :
                    `<button onclick="manager.installExtension('${ext.name}', '${ext.url}')">📥 Установить</button>`
                }
            </div>
        `;

        return card;
    }

    async installExtension(name, url) {
        const result = await this.apiCall(`/install/${name}?url=${encodeURIComponent(url)}`);
        if (result && result.success) {
            this.showMessage(result.message);
            await this.loadInstalledExtensions();
        } else if (result) {
            this.showMessage(result.message, 'error');
        }
    }

    async deleteExtension(name) {
        if (confirm(`Удалить расширение "${name}"?`)) {
            const result = await this.apiCall(`/delete/${name}`);
            if (result && result.success) {
                this.showMessage(result.message);
                await this.loadInstalledExtensions();
            } else if (result) {
                this.showMessage(result.message, 'error');
            }
        }
    }

    showMessage(text, type = 'success') {
        const message = document.getElementById('message');
        message.textContent = text;
        message.className = `message ${type}`;
        
        setTimeout(() => {
            message.className = 'message hidden';
        }, 3000);
    }

    setupEventListeners() {
        // Автозагрузка удаленных расширений при переходе на вкладку
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                if (btn.textContent.includes('Доступные')) {
                    this.loadRemoteExtensions();
                }
            });
        });
    }

    // Эти методы будут реализованы в основном приложении
    openAdditionsFolder() {
        this.showMessage('Функция откроется в основном приложении');
    }

    reloadBrowser() {
        this.showMessage('Браузер перезагрузится');
    }

    clearCache() {
        this.showMessage('Кэш очищен');
    }
}

// Функции для управления вкладками
function showTab(tabName) {
    // Скрыть все вкладки
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Показать выбранную вкладку
    document.getElementById(`${tabName}-tab`).classList.add('active');
    
    // Обновить кнопки
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
}

// Глобальный экземпляр менеджера
const manager = new ExtensionManager();

// Глобальные функции для HTML
function loadRemoteExtensions() {
    manager.loadRemoteExtensions();
}

function openAdditionsFolder() {
    manager.openAdditionsFolder();
}

function reloadBrowser() {
    manager.reloadBrowser();
}

function clearCache() {
    manager.clearCache();
}
