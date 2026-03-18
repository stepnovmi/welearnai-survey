// Drag and drop for ranking cards
const list = document.getElementById('sortable-list');
let dragItem = null;

// Desktop drag events
list.addEventListener('dragstart', (e) => {
    dragItem = e.target.closest('.card');
    if (dragItem) dragItem.classList.add('dragging');
});

list.addEventListener('dragend', () => {
    if (dragItem) dragItem.classList.remove('dragging');
    document.querySelectorAll('.card').forEach(c => c.classList.remove('drag-over'));
    dragItem = null;
    updateRanks();
});

list.addEventListener('dragover', (e) => {
    e.preventDefault();
    const target = e.target.closest('.card');
    if (target && target !== dragItem) {
        document.querySelectorAll('.card').forEach(c => c.classList.remove('drag-over'));
        target.classList.add('drag-over');
        const rect = target.getBoundingClientRect();
        const mid = rect.top + rect.height / 2;
        if (e.clientY < mid) {
            list.insertBefore(dragItem, target);
        } else {
            list.insertBefore(dragItem, target.nextSibling);
        }
    }
});

// Touch events for mobile
let touchItem = null;
let touchClone = null;
let touchStartY = 0;

list.addEventListener('touchstart', (e) => {
    const card = e.target.closest('.card');
    if (!card || e.target.closest('.btn-move')) return;

    touchItem = card;
    touchStartY = e.touches[0].clientY;
    const rect = card.getBoundingClientRect();

    touchClone = card.cloneNode(true);
    touchClone.style.position = 'fixed';
    touchClone.style.top = rect.top + 'px';
    touchClone.style.left = rect.left + 'px';
    touchClone.style.width = rect.width + 'px';
    touchClone.style.zIndex = '1000';
    touchClone.style.opacity = '0.9';
    touchClone.style.boxShadow = '0 8px 32px rgba(0,0,0,0.15)';
    touchClone.style.pointerEvents = 'none';

    setTimeout(() => {
        document.body.appendChild(touchClone);
        touchItem.style.opacity = '0.3';
    }, 100);
}, { passive: true });

list.addEventListener('touchmove', (e) => {
    if (!touchItem || !touchClone) return;
    e.preventDefault();

    const touchY = e.touches[0].clientY;
    const delta = touchY - touchStartY;
    const origRect = touchItem.getBoundingClientRect();
    touchClone.style.top = (origRect.top + delta) + 'px';

    const cards = [...list.querySelectorAll('.card')];
    for (const card of cards) {
        if (card === touchItem) continue;
        const rect = card.getBoundingClientRect();
        const mid = rect.top + rect.height / 2;
        if (touchY > rect.top && touchY < rect.bottom) {
            if (touchY < mid) {
                list.insertBefore(touchItem, card);
            } else {
                list.insertBefore(touchItem, card.nextSibling);
            }
            break;
        }
    }
}, { passive: false });

list.addEventListener('touchend', () => {
    if (touchClone) {
        touchClone.remove();
        touchClone = null;
    }
    if (touchItem) {
        touchItem.style.opacity = '1';
        touchItem = null;
    }
    updateRanks();
});

// Button controls
function moveUp(btn) {
    const card = btn.closest('.card');
    const prev = card.previousElementSibling;
    if (prev) {
        list.insertBefore(card, prev);
        updateRanks();
    }
}

function moveDown(btn) {
    const card = btn.closest('.card');
    const next = card.nextElementSibling;
    if (next) {
        list.insertBefore(next, card);
        updateRanks();
    }
}

function updateRanks() {
    const cards = list.querySelectorAll('.card');
    cards.forEach((card, i) => {
        card.querySelector('.card-rank').textContent = i + 1;
    });
}

function submitRanking() {
    const cards = list.querySelectorAll('.card');
    const ranking = [...cards].map(c => parseInt(c.dataset.id));
    const expectations = document.getElementById('expectations-input').value.trim();

    const btn = document.getElementById('submit-btn');
    btn.disabled = true;
    btn.textContent = 'Отправка...';

    fetch('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ranking, expectations })
    })
    .then(res => {
        if (res.status === 403) {
            alert('Опрос завершён');
            window.location.reload();
            return;
        }
        return res.json();
    })
    .then(data => {
        if (data && data.status === 'ok') {
            document.getElementById('submit-btn').style.display = 'none';
            document.querySelector('.cards-container').style.display = 'none';
            document.getElementById('expectations-section').style.display = 'none';
            document.getElementById('success-message').classList.add('show');
        }
    })
    .catch(() => {
        btn.disabled = false;
        btn.textContent = 'Отправить';
        alert('Ошибка отправки, попробуйте ещё раз');
    });
}
