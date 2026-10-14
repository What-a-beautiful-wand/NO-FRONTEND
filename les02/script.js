// Товары

let PRODUCTS = [
    {
        id: 1,
        title: 'Meteora',
        group_name: 'Linkin Park',
        price: 5400,
        img_name: 'Обложка альбома Meteora',
        img_href: 'https://upload.wikimedia.org/wikipedia/ru/4/44/Meteora_%28%D0%BE%D0%B1%D0%BB%D0%BE%D0%B6%D0%BA%D0%B0_%D0%B0%D0%BB%D1%8C%D0%B1%D0%BE%D0%BC%D0%B0%2C_2003%29.jpg?utm_source=ru.wikipedia.org&utm_campaign=index&utm_content=original',
        like: false,
        year: 2003,
        duration: '36:35',
        quantity: 13
    },
    {
        id: 2,
        title: 'Trench',
        group_name: 'Twenty One Pilots',
        price: 4999,
        img_name: 'Обложка альбома Trench',
        img_href: 'https://thumb.wikimedia.org/wikipedia/ru/thumb/c/c7/Trench_cover.jpg/330px-Trench_cover.jpg?utm_source=ru.wikipedia.org&utm_campaign=parser&utm_content=thumbnail',
        like: false,
        year: 2018,
        duration: '56:04',
        quantity: 14
    },
    {
        id: 3,
        title: 'The 2nd Law',
        group_name: 'Muse',
        price: 4699,
        img_name: 'Обложка альбома The 2nd Law',
        img_href: 'https://upload.wikimedia.org/wikipedia/en/3/35/Muse_2nd_law.jpg?utm_source=en.wikipedia.org&utm_campaign=index&utm_content=original',
        like: true,
        year: 2012,
        duration: '53:49',
        quantity: 13
    }
];

// Элементы страницы

const CATALOG = document.querySelector('.cards_section');
const HEADER = document.querySelector('header');
const COMPARISON_CONTAINER = document.querySelector('.table_container');
const COMPARISON_BODY = document.querySelector('.comparsion_table tbody');
const PRODUCT_FORM = document.querySelector('.product_form');
const PRODUCT_STATUS = document.querySelector('.product_status');

const countText = document.createElement('p');
countText.className = 'catalog_count_text';
countText.setAttribute('aria-live', 'polite');

// Запуск

updateCatalogCount();
HEADER.append(countText);

if (PRODUCTS.length === 0) {
    showEmptyCatalog();
} else {
    renderCardsCatalog();
    renderComparisonTable();
}

CATALOG.addEventListener('click', handleCatalogClick);
PRODUCT_FORM.addEventListener('submit', addProduct);
PRODUCT_FORM.addEventListener('input', () => {
    PRODUCT_STATUS.textContent = '';
});

// Кнопки карточек

function handleCatalogClick(event) {
    const button = event.target.closest('.favorite_button, .delete_button');

    if (!button || !CATALOG.contains(button)) {
        return;
    }

    const card = button.closest('.card');

    if (!card) {
        return;
    }

    const productId = Number(card.dataset.productId);

    if (button.classList.contains('delete_button')) {
        deleteProduct(productId);
        return;
    }

    const product = PRODUCTS.find(item => item.id === productId);

    if (!product) {
        return;
    }

    const updatedProduct = { ...product, like: !product.like };
    PRODUCTS = PRODUCTS.map(item => item.id === productId ? updatedProduct : item);
    card.classList.toggle('card_like', updatedProduct.like);
    updateFavoriteButton(button, updatedProduct);
    updateCatalogCount();
}

// Добавление товара

function addProduct(event) {
    event.preventDefault();

    if (!PRODUCT_FORM.reportValidity()) {
        return;
    }

    const fields = PRODUCT_FORM.elements;
    const title = fields.title.value.trim();
    const bandName = fields.group_name.value.trim(); // почаще трим надо 

    if (!title || !bandName) {
        PRODUCT_STATUS.textContent = 'Введите название альбома и исполнителя.';
        return;
    }

    const product = {
        id: PRODUCTS.reduce((maxId, item) => Math.max(maxId, item.id), 0) + 1,
        title,
        group_name: bandName,
        price: Number(fields.price.value),
        img_name: `Обложка альбома ${title}`,
        img_href: fields.img_href.value.trim(),
        like: false,
        year: Number(fields.year.value),
        duration: fields.duration.value.trim(),
        quantity: Number(fields.quantity.value)
    };

    PRODUCTS = [...PRODUCTS, product];
    CATALOG.querySelector('.error_text')?.remove();
    COMPARISON_CONTAINER.querySelector('.error_text')?.remove();
    COMPARISON_BODY.closest('table').hidden = false;
    renderCardsCatalog([product]);
    renderComparisonTable([product]);
    updateCatalogCount();
    PRODUCT_FORM.reset();
    PRODUCT_STATUS.textContent = `Товар «${title}» добавлен в каталог.`;
}

// Удаление товара

function deleteProduct(productId) {
    if (!PRODUCTS.some(product => product.id === productId)) {
        return;
    }

    PRODUCTS = PRODUCTS.filter(product => product.id !== productId);
    CATALOG.querySelector(`[data-product-id="${productId}"]`)?.remove();
    COMPARISON_BODY.querySelector(`[data-product-id="${productId}"]`)?.remove();
    updateCatalogCount();

    if (PRODUCTS.length === 0) {
        showEmptyCatalog();
    }
}

// Пустой каталог

function showEmptyCatalog() {
    const catalogError = document.createElement('p');
    catalogError.className = 'error_text';
    catalogError.textContent = 'Каталог пуст';
    CATALOG.append(catalogError);

    const comparisonError = document.createElement('p');
    comparisonError.className = 'error_text';
    comparisonError.textContent = 'Нет товаров для сравнения';
    COMPARISON_BODY.closest('table').hidden = true;
    COMPARISON_CONTAINER.append(comparisonError);
}

// Таблица сравнения

function renderComparisonTable(products = PRODUCTS) {
    for (const product of products) {
        const row = document.createElement('tr');
        row.dataset.productId = product.id;
        const values = [
            product.title,
            product.group_name,
            product.year,
            product.duration,
            product.quantity
        ];

        for (const value of values) {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.append(cell);
        }

        COMPARISON_BODY.append(row);
    }
}

// Карточки товаров

function renderCardsCatalog(products = PRODUCTS) {
    for (const product of products) {
        const card = document.createElement('article');
        card.className = `card ${product.like ? 'card_like' : ''}`;
        card.dataset.productId = product.id;

        const favoriteButton = document.createElement('button');
        favoriteButton.type = 'button';
        favoriteButton.className = 'favorite_button';

        updateFavoriteButton(favoriteButton, product);

        const info = document.createElement('p');
        info.className = 'card_text';

        const albumName = document.createElement('span');
        albumName.className = 'albom_name';
        albumName.textContent = product.title;

        const bandName = document.createElement('span');
        bandName.className = 'albom_band_name';
        bandName.textContent = product.group_name;
        info.append(albumName, document.createElement('br'), bandName);

        const figure = document.createElement('figure');
        figure.className = 'card_figure';

        const image = document.createElement('img');
        image.className = 'card_image';
        image.src = product.img_href;
        image.alt = product.img_name;
        figure.append(image);

        const price = document.createElement('span');
        price.className = 'price_text';
        price.textContent = `${product.price.toLocaleString('ru-RU')} ₽`;

        const deleteButton = document.createElement('button');
        deleteButton.type = 'button';
        deleteButton.className = 'delete_button';
        deleteButton.textContent = '−';
        deleteButton.title = `Удалить товар: ${product.title}`;
        deleteButton.setAttribute('aria-label', `Удалить товар: ${product.title}`);

        card.append(favoriteButton, info, figure, price, deleteButton);
        CATALOG.append(card);
    }
}

// Счётчик и избранное

function updateCatalogCount() {
    const favoritesCount = PRODUCTS.filter(product => product.like).length;
    countText.textContent = `Всего товаров в каталоге — ${PRODUCTS.length}, ` +
        `из них в избранном — ${favoritesCount}`;
}

function updateFavoriteButton(favoriteButton, product) {
    const action = product.like ? 'Убрать из избранного' : 'Добавить в избранное';
    const label = `${action}: ${product.title}`;

    favoriteButton.textContent = product.like ? '♥' : '♡';
    favoriteButton.setAttribute('aria-pressed', String(product.like));
    favoriteButton.setAttribute('aria-label', label);
    favoriteButton.title = label;
}
