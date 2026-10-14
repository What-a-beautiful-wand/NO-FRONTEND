const PRODUCTS = [
    {id:1, title:'Meteora', group_name:'Linkin Park', price:5400,
        img_name: 'Обложка альбома Meteora', img_href: 'https://upload.wikimedia.org/wikipedia/ru/4/44/Meteora_%28%D0%BE%D0%B1%D0%BB%D0%BE%D0%B6%D0%BA%D0%B0_%D0%B0%D0%BB%D1%8C%D0%B1%D0%BE%D0%BC%D0%B0%2C_2003%29.jpg?utm_source=ru.wikipedia.org&utm_campaign=index&utm_content=original',
        available: true,
        year:2003, duration:'36:35', quantity:13
    },
    {id:2, title: 'Trench', group_name:'Twenty One Pilots', price:4999,
        img_name: 'Обложка альбома Trench', img_href: 'https://thumb.wikimedia.org/wikipedia/ru/thumb/c/c7/Trench_cover.jpg/330px-Trench_cover.jpg?utm_source=ru.wikipedia.org&utm_campaign=parser&utm_content=thumbnail',
        available: true,
        year:2018 , duration:'56:04', quantity:14
    },
    {id:3, title: 'The 2nd Law', group_name:'Muse', price: 4699,
        img_name: 'Обложка альбома The 2nd Law', img_href:'https://upload.wikimedia.org/wikipedia/en/3/35/Muse_2nd_law.jpg?utm_source=en.wikipedia.org&utm_campaign=index&utm_content=original',
        available: false,
        year:2012 , duration:'53:49', quantity:13
    }
];
    
const CATALOG = document.querySelector('.cards_section');
const HEADER = document.querySelector('header');
const COMPARISON_CONTAINER = document.querySelector('.table_container');
const COMPARISON_BODY = document.querySelector('.comparsion_table tbody');


const countText = document.createElement('p');
countText.className = 'catalog_count_text';
countText.textContent = `Всего товаров в каталоге — ${PRODUCTS.length}`;
HEADER.append(countText);

if (PRODUCTS.length === 0) {
    const catalogError = document.createElement('p');
    catalogError.className = 'error_text';
    catalogError.textContent = 'Каталог пуст';
    CATALOG.append(catalogError);

    const comparisonError = document.createElement('p');
    comparisonError.className = 'error_text';
    comparisonError.textContent = 'Нет товаров для сравнения';
    COMPARISON_CONTAINER.replaceChildren(comparisonError);
} else {
    render_cards_catalog();
    render_comparsion_table();
}

function render_comparsion_table() {

    for (const product of PRODUCTS) {
        const row = document.createElement('tr');
        row.dataset.productId = product.id;
        for (const value of [product.title, product.group_name, product.year, product.duration, product.quantity]) {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.append(cell);
        };
        COMPARISON_BODY.append(row);
    };
};

function render_cards_catalog() {

    for (const product of PRODUCTS) {
        const card = document.createElement('article');
        card.className = product.available ? 'card' : 'card_unavailable';
        card.dataset.productId = product.id;

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

        card.append(info, figure, price);
        CATALOG.append(card);
    };
};