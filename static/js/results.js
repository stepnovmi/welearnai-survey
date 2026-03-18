const TOPICS = [
    { id: 1, icon: '🧠', title: 'Основы работы нейросетей', color: '#003082', category: 'Теория' },
    { id: 2, icon: '💼', title: 'Принципы внедрения ИИ в бизнес', color: '#003082', category: 'Теория' },
    { id: 3, icon: '✍️', title: 'Основы промптинга', color: '#0E7C47', category: 'Практика' },
    { id: 4, icon: '🔧', title: 'Создание агента в NoCode (n8n)', color: '#0E7C47', category: 'Практика' },
    { id: 5, icon: '🏭', title: 'ДаВинчи и корп. системы', color: '#E31E24', category: 'Демо' },
    { id: 6, icon: '🚀', title: 'Разработка ПО за 2 часа вместо 2 лет', color: '#E31E24', category: 'Демо' },
    { id: 7, icon: '📊', title: 'Применение ИИ в вашей области', color: '#7C3AED', category: 'Кейс-стади' }
];

let isActive = true;
let pendingAction = null;

function fetchStats() {
    fetch('/api/stats')
        .then(r => r.json())
        .then(data => {
            document.getElementById('total-count').textContent = data.total;
            isActive = data.is_active;
            updateToggleButton();
            renderChart(data.avg_ranks);
        })
        .catch(console.error);
}

function renderChart(avgRanks) {
    const container = document.getElementById('chart-container');

    // Sort topics by average rank (lower = better)
    const sorted = TOPICS.map(t => ({
        ...t,
        avg: avgRanks && avgRanks[t.id] !== undefined ? avgRanks[t.id] : 4
    })).sort((a, b) => a.avg - b.avg);

    const maxScore = 7;

    container.innerHTML = sorted.map(t => {
        const score = (maxScore - t.avg + 1).toFixed(1);
        const pct = ((maxScore - t.avg + 1) / maxScore * 100).toFixed(0);
        return `
            <div class="chart-row">
                <div class="chart-label">
                    <span class="chart-icon">${t.icon}</span>
                    <span class="chart-name">${t.title}</span>
                </div>
                <div class="chart-bar-container">
                    <div class="chart-bar" style="width: ${pct}%; background: ${t.color}"></div>
                </div>
                <div class="chart-score">${score}</div>
            </div>
        `;
    }).join('');
}

function updateToggleButton() {
    const btn = document.getElementById('toggle-btn');
    if (isActive) {
        btn.textContent = 'Остановить';
        btn.className = 'btn-toggle active';
    } else {
        btn.textContent = 'Запустить';
        btn.className = 'btn-toggle inactive';
    }
}

function toggleSurvey() {
    const modal = document.getElementById('modal-overlay');
    const title = document.getElementById('modal-title');
    const text = document.getElementById('modal-text');
    const confirmBtn = document.getElementById('modal-confirm');

    if (isActive) {
        pendingAction = 'deactivate';
        title.textContent = 'Остановить опрос?';
        text.textContent = 'Новые ответы не будут приниматься. Данные сохранятся.';
        confirmBtn.className = 'modal-btn modal-confirm deactivate';
        confirmBtn.textContent = 'Остановить';
    } else {
        pendingAction = 'activate';
        title.textContent = 'Запустить опрос?';
        text.textContent = 'Все предыдущие ответы будут удалены. Опрос начнётся заново.';
        confirmBtn.className = 'modal-btn modal-confirm activate';
        confirmBtn.textContent = 'Запустить';
    }

    modal.classList.add('show');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('show');
    pendingAction = null;
}

function confirmAction() {
    if (!pendingAction) return;

    fetch(`/api/${pendingAction}`, { method: 'POST' })
        .then(r => r.json())
        .then(() => {
            closeModal();
            fetchStats();
        })
        .catch(console.error);
}

function exportCSV() {
    window.location.href = '/api/export';
}

// Initial load and polling
fetchStats();
setInterval(fetchStats, 5000);
