import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None, headers=None):
        self.status, self.code, self.message = status, code, message
        self.details, self.headers = details, headers


def error_response(status, code, message, details=None, headers=None):
    return JSONResponse(status_code=status, content={
        'error': {'code': code, 'message': message, 'details': details},
    }, headers=headers)


def install_handlers(app: FastAPI):
    @app.exception_handler(APIError)
    async def api_error(request: Request, exc: APIError):
        return error_response(exc.status, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [{'field': '.'.join(map(str, e['loc'])), 'message': e['msg'], 'type': e['type']}
                   for e in exc.errors()]
        return error_response(422, 'validation_error', 'Проверьте поля запроса', details)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(exc.status_code, 'not_found' if exc.status_code == 404 else 'http_error',
                              str(exc.detail), headers=exc.headers)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.error('Unhandled API error', exc_info=exc)
        return error_response(500, 'internal_error', 'Внутренняя ошибка сервера')
