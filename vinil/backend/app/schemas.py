"""Public API contracts. Monetary values are integer Russian rubles."""
from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r'^[+0-9() -]{7,40}$')]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]
ShippingMethod = Literal['pickup', 'courier']
OrderStatus = Literal['pending', 'processing', 'shipped', 'completed', 'cancelled']
T = TypeVar('T')


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int
    pages: int


class ProductInput(Input):
    title: Text
    group_name: Text
    price: int = Field(gt=0, le=10000000)
    img_href: str = Field(min_length=1, max_length=2000)
    year: int = Field(gt=0, le=2100)
    duration: str = Field(pattern=r'^[0-9]+:[0-5][0-9]$')
    quantity: int = Field(ge=0, le=1000000)
    genre: Text = 'Rock'
    description: str = Field(default='', max_length=10000)
    label: str = Field(default='', max_length=200)
    format: Literal['LP', '2LP', 'EP', 'Single'] = 'LP'
    rpm: Literal[33, 45] = 33
    condition: Literal['new', 'used'] = 'new'
    is_active: bool = True

    @field_validator('img_href')
    @classmethod
    def validate_image_url(cls, value: str) -> str:
        from urllib.parse import urlsplit
        url = urlsplit(value)
        if url.scheme in ('http', 'https') and url.netloc:
            return value
        if value.startswith(('/media/', '/mocks/media/')) and '..' not in url.path.split('/'):
            return value
        raise ValueError('Укажите http(s)-ссылку или локальный путь /media/ либо /mocks/media/')


class Product(ProductInput):
    model_config = ConfigDict(extra='ignore')
    id: int
    quantity: int = Field(ge=0)
    img_name: str
    like: bool = False
    created_at: datetime
    updated_at: datetime


class RegisterInput(Input):
    email: EmailStr
    password: Password
    name: Name
    phone: str = Field(default='', max_length=40)

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, value: str) -> str:
        import re
        value = value.strip()
        if value and (not re.fullmatch(r'[+0-9() -]{7,40}', value) or not 7 <= sum(c.isdigit() for c in value) <= 15):
            raise ValueError('Некорректный телефон')
        return value


class LoginInput(Input):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)


class User(BaseModel):
    id: int
    email: str
    name: str
    phone: str
    role: Literal['customer', 'admin']
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal['bearer'] = 'bearer'
    expires_at: datetime
    user: User


class ProfileInput(Input):
    name: Name
    phone: str = Field(default='', max_length=40)
    _phone_validator = field_validator('phone')(RegisterInput.validate_phone.__func__)


class PasswordInput(Input):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: Password
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)


class CartItem(BaseModel):
    product: Product
    quantity: int
    line_total: int
    available: bool


class Cart(BaseModel):
    items: list[CartItem]
    items_count: int
    subtotal: int
    currency: Literal['RUB'] = 'RUB'


class CartQuantity(Input):
    quantity: int = Field(ge=1, le=99)


class QuoteInput(Input):
    shipping_method: ShippingMethod


class Quote(BaseModel):
    cart: Cart
    shipping_method: ShippingMethod
    subtotal: int
    delivery_fee: int
    total: int
    currency: Literal['RUB'] = 'RUB'


class CheckoutInput(QuoteInput):
    recipient_name: Name
    phone: Phone
    address: str = Field(default='', max_length=1000)
    comment: str = Field(default='', max_length=2000)
    payment_method: Literal['on_receipt'] = 'on_receipt'
    expected_subtotal: int | None = Field(default=None, ge=0)

    _phone_validator = field_validator('phone')(RegisterInput.validate_phone.__func__)

    @model_validator(mode='after')
    def require_address(self):
        if self.shipping_method == 'courier' and len(self.address) < 10:
            raise ValueError('Для курьерской доставки укажите адрес (не менее 10 символов)')
        if self.shipping_method == 'pickup':
            self.address = ''
        return self


class OrderItem(BaseModel):
    product_id: int
    title: str
    group_name: str
    img_href: str
    unit_price: int
    quantity: int
    line_total: int


class OrderEvent(BaseModel):
    status: OrderStatus
    created_at: datetime


class Order(BaseModel):
    id: int
    number: str
    user_id: int
    status: OrderStatus
    payment_method: Literal['on_receipt']
    payment_status: Literal['unpaid', 'paid']
    shipping_method: ShippingMethod
    recipient_name: str
    email: str
    phone: str
    address: str
    comment: str
    subtotal: int
    delivery_fee: int
    total: int
    currency: Literal['RUB']
    items: list[OrderItem]
    history: list[OrderEvent]
    created_at: datetime
    updated_at: datetime


class OrderStatusInput(Input):
    status: OrderStatus


class ContactInput(Input):
    email: EmailStr
    tel: str = Field(default='', max_length=40)
    problem_text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]


class MessageReceipt(BaseModel):
    id: int
    status: Literal['received'] = 'received'
    created_at: datetime


class Message(BaseModel):
    id: int
    email: str
    tel: str
    problem_text: str
    status: Literal['open', 'resolved']
    created_at: datetime


class MessageStatusInput(Input):
    status: Literal['open', 'resolved']


class UploadResponse(BaseModel):
    img_href: str
    width: int
    height: int


class CatalogFilters(BaseModel):
    genres: list[str]
    artists: list[str]
    formats: list[str]
    price_min: int | None
    price_max: int | None
    year_min: int | None
    year_max: int | None


class ShippingOption(BaseModel):
    id: ShippingMethod
    title: str
    fee: int
    address: str | None = None
    free_from: int | None = None


class PaymentOption(BaseModel):
    id: Literal['on_receipt']
    title: str


class CheckoutOptions(BaseModel):
    currency: Literal['RUB'] = 'RUB'
    shipping_methods: list[ShippingOption]
    payment_methods: list[PaymentOption]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: object = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody
