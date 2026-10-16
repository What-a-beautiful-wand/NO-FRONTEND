const API = '/api';
let PRODUCTS = [];

const CATALOG = document.querySelector('.cards_section');
const SORT_SELECT = document.querySelector('#catalog-sort');
const HEADER = document.querySelector('header');
const COMPARISON_CONTAINER = document.querySelector('.table_container');
const COMPARISON_BODY = document.querySelector('.comparsion_table tbody');
const PRODUCT_FORM = document.querySelector('.product_form');
const PRODUCT_STATUS = document.querySelector('.product_status');
const CONTACT_FORM = document.querySelector('.connection_form');
const CONTACT_STATUS = document.querySelector('.connection_status');

const countText = document.createElement('p');
countText.className = 'catalog_count_text';
countText.setAttribute('aria-live', 'polite');
HEADER.append(countText);

CATALOG.addEventListener('click', handleCatalogClick);
SORT_SELECT.addEventListener('change', renderCatalog);
PRODUCT_FORM.addEventListener('submit', addProduct);
CONTACT_FORM.addEventListener('submit', sendMessage);
PRODUCT_FORM.addEventListener('input', () => { PRODUCT_STATUS.textContent = ''; });
CONTACT_FORM.addEventListener('input', () => { CONTACT_STATUS.textContent = ''; });

initialize();

async function apiRequest(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
        ...options,
        headers: { 'Content-Type': 'application/json', ...options.headers }
    });
    const result = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
        const detail = Array.isArray(result?.detail)
            ? result.detail.map(item => item.msg).join(' ')
            : result?.detail;
        throw new Error(detail || `Ошибка сервера (${response.status})`);
    }
    return result;
}

async function initialize() {
    try {
        PRODUCTS = await apiRequest('/products');
        renderCatalog();
        renderComparisonTable();
        updateCatalogCount();
    } catch (error) {
        showCatalogError(`Не удалось загрузить каталог: ${error.message}`);
        updateCatalogCount();
    }
}

function handleCatalogClick(event) {
    const button = event.target.closest('.favorite_button, .delete_button');
    if (!button || !CATALOG.contains(button)) return;

    const card = button.closest('.card');
    const productId = Number(card?.dataset.productId);
    if (!productId) return;

    if (button.classList.contains('favorite_button')) {
        toggleFavorite(productId);
    } else {
        deleteProduct(productId);
    }
}

async function toggleFavorite(productId) {
    try {
        const updated = await apiRequest(`/products/${productId}/favorite`, { method: 'PATCH' });
        PRODUCTS = PRODUCTS.map(product => product.id === productId ? updated : product);
        renderCatalog();
        updateCatalogCount();
    } catch (error) {
        PRODUCT_STATUS.textContent = `Не удалось изменить избранное: ${error.message}`;
    }
}

async function deleteProduct(productId) {
    try {
        await apiRequest(`/products/${productId}`, { method: 'DELETE' });
        PRODUCTS = PRODUCTS.filter(product => product.id !== productId);
        renderCatalog();
        renderComparisonTable();
        updateCatalogCount();
    } catch (error) {
        PRODUCT_STATUS.textContent = `Не удалось удалить товар: ${error.message}`;
    }
}

async function addProduct(event) {
    event.preventDefault();
    if (!PRODUCT_FORM.reportValidity()) return;

    const fields = PRODUCT_FORM.elements;
    const data = {
        title: fields.title.value.trim(),
        group_name: fields.group_name.value.trim(),
        price: Number(fields.price.value),
        img_href: fields.img_href.value.trim(),
        year: Number(fields.year.value),
        duration: fields.duration.value.trim(),
        quantity: Number(fields.quantity.value)
    };

    try {
        const product = await apiRequest('/products', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        PRODUCTS.push(product);
        renderCatalog();
        renderComparisonTable();
        updateCatalogCount();
        PRODUCT_FORM.reset();
        PRODUCT_STATUS.textContent = `Товар «${product.title}» добавлен в каталог.`;
    } catch (error) {
        PRODUCT_STATUS.textContent = `Не удалось добавить товар: ${error.message}`;
    }
}

async function sendMessage(event) {
    event.preventDefault();
    if (!CONTACT_FORM.reportValidity()) return;

    const fields = CONTACT_FORM.elements;
    try {
        await apiRequest('/messages', {
            method: 'POST',
            body: JSON.stringify({
                email: fields.email.value.trim(),
                tel: fields.tel.value.trim(),
                problem_text: fields.problem_text.value.trim()
            })
        });
        CONTACT_FORM.reset();
        CONTACT_STATUS.textContent = 'Сообщение отправлено. Спасибо!';
    } catch (error) {
        CONTACT_STATUS.textContent = `Не удалось отправить сообщение: ${error.message}`;
    }
}

function renderCatalog() {
    CATALOG.replaceChildren();
    if (PRODUCTS.length === 0) {
        showCatalogError('Каталог пуст. Добавьте первую пластинку в форме ниже.');
        return;
    }

    const products = [...PRODUCTS];
    switch (SORT_SELECT.value) {
        case 'favorites': products.sort((a, b) => Number(b.like) - Number(a.like)); break;
        case 'price-asc': products.sort((a, b) => a.price - b.price); break;
        case 'price-desc': products.sort((a, b) => b.price - a.price); break;
        case 'artist': products.sort((a, b) => a.group_name.localeCompare(b.group_name, 'ru')); break;
        case 'title': products.sort((a, b) => a.title.localeCompare(b.title, 'ru')); break;
        default: products.sort((a, b) => a.id - b.id);
    }

    for (const product of products) CATALOG.append(createCard(product));
}

function createCard(product) {
    const card = document.createElement('article');
    card.className = `card ${product.like ? 'card_like' : ''}`;
    card.dataset.productId = product.id;

    const favorite = document.createElement('button');
    favorite.type = 'button';
    favorite.className = 'favorite_button';
    favorite.textContent = product.like ? '♥' : '♡';
    favorite.setAttribute('aria-pressed', String(product.like));
    favorite.setAttribute('aria-label', `${product.like ? 'Убрать из' : 'Добавить в'} избранное: ${product.title}`);

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'delete_button';
    remove.textContent = '−';
    remove.title = `Удалить товар: ${product.title}`;
    remove.setAttribute('aria-label', remove.title);

    const info = document.createElement('p');
    info.className = 'card_text';
    const title = document.createElement('span');
    title.className = 'albom_name';
    title.textContent = product.title;
    const artist = document.createElement('span');
    artist.className = 'albom_band_name';
    artist.textContent = product.group_name;
    info.append(title, document.createElement('br'), artist);

    const figure = document.createElement('figure');
    figure.className = 'card_figure';
    const image = document.createElement('img');
    image.className = 'card_image';
    image.src = product.img_href;
    image.alt = product.img_name;
    image.loading = 'lazy';
    figure.append(image);

    const price = document.createElement('span');
    price.className = 'price_text';
    price.textContent = `${Number(product.price).toLocaleString('ru-RU')} ₽`;
    card.append(favorite, info, figure, price, remove);
    return card;
}

function renderComparisonTable() {
    COMPARISON_BODY.replaceChildren();
    COMPARISON_BODY.closest('table').hidden = PRODUCTS.length === 0;
    COMPARISON_CONTAINER.querySelector('.error_text')?.remove();

    if (PRODUCTS.length === 0) {
        const message = document.createElement('p');
        message.className = 'error_text';
        message.textContent = 'Нет товаров для сравнения';
        COMPARISON_CONTAINER.append(message);
        return;
    }

    for (const product of PRODUCTS) {
        const row = document.createElement('tr');
        for (const value of [product.title, product.group_name, product.year, product.duration, product.quantity]) {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.append(cell);
        }
        COMPARISON_BODY.append(row);
    }
}

function showCatalogError(message) {
    CATALOG.replaceChildren();
    const error = document.createElement('p');
    error.className = 'error_text';
    error.textContent = message;
    CATALOG.append(error);
}

function updateCatalogCount() {
    const favoritesCount = PRODUCTS.filter(product => product.like).length;
    countText.textContent = `Всего товаров в каталоге — ${PRODUCTS.length}, из них в избранном — ${favoritesCount}`;
}
