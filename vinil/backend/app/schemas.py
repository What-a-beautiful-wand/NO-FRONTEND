"""Request and response contracts. Prices are integer Russian rubles."""

import re

from pydantic import BaseModel, Field, field_validator


class ProductInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    group_name: str = Field(min_length=1, max_length=200)
    price: int = Field(gt=0)
    img_href: str = Field(min_length=1, max_length=2000)
    year: int = Field(gt=0, le=2100)
    duration: str = Field(pattern=r"^[0-9]+:[0-5][0-9]$")
    quantity: int = Field(ge=0)

    @field_validator("title", "group_name")
    @classmethod
    def trim_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Поле не должно быть пустым")
        return value

    @field_validator("img_href")
    @classmethod
    def validate_image_url(cls, value: str) -> str:
        value = value.strip()
        if not (re.match(r"^https?://", value, re.IGNORECASE) or value.startswith("/media/")):
            raise ValueError("Укажите http(s)-ссылку или локальный путь /media/")
        return value


class Product(ProductInput):
    id: int
    img_name: str
    like: bool


class ContactInput(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    tel: str = Field(default="", max_length=40)
    problem_text: str = Field(min_length=1, max_length=10000)

    @field_validator("email", "tel", "problem_text")
    @classmethod
    def trim_values(cls, value: str) -> str:
        return value.strip()

    @field_validator("email", "problem_text")
    @classmethod
    def require_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("Поле не должно быть пустым")
        return value
